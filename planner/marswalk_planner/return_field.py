"""Champ de temps de retour (P3).

Algorithme de Dijkstra multi-source sur la grille de coût, depuis l'habitat
vers toutes les cases accessibles (8 directions, diagonales × √2).
Implémentation vectorisée avec scipy.sparse.csgraph pour tenir en < 2 s
sur une grille de 1000 × 1000 cases.

Signature gelée : ``return_field(cost_grid, habitat, suit) -> ReturnField``.

Sources : see docs/science/hypotheses-marche.md §6.
"""

from __future__ import annotations

import math

import numpy as np
import scipy.sparse
import scipy.sparse.csgraph

from marswalk_core.geodesy import to_analysis
from marswalk_core.grids import CostGrid, ReturnField
from marswalk_core.schemas import LonLat, SuitModel


def _build_graph(cost: np.ndarray) -> scipy.sparse.csr_matrix:
    """Construit le graphe orienté pondéré de la grille en CSR.

    Les 8 voisins sont connectés. Le poids d'un arc (i → j) est
    cost[j] × facteur_direction, ce qui représente le coût d'entrée dans j.
    Les cases interdites (coût infini ou NaN) sont exclues.
    """
    height, width = cost.shape
    n = height * width

    flat = cost.ravel().astype(np.float64)
    # Masque des cases passables
    passable = np.isfinite(flat)

    # Directions : (dr, dc, weight_factor)
    dirs = [
        (-1, 0, 1.0),
        (1, 0, 1.0),
        (0, -1, 1.0),
        (0, 1, 1.0),
        (-1, -1, math.sqrt(2.0)),
        (-1, 1, math.sqrt(2.0)),
        (1, -1, math.sqrt(2.0)),
        (1, 1, math.sqrt(2.0)),
    ]

    rows_list = []
    cols_list = []
    data_list = []

    rows_idx = np.arange(n).reshape(height, width)

    for dr, dc, wf in dirs:
        # Source cells
        r_src = slice(max(0, dr), height + min(0, dr)) if dr != 0 else slice(None)
        c_src = slice(max(0, dc), width + min(0, dc)) if dc != 0 else slice(None)
        # Destination cells
        r_dst = slice(max(0, -dr), height + min(0, -dr)) if dr != 0 else slice(None)
        c_dst = slice(max(0, -dc), width + min(0, -dc)) if dc != 0 else slice(None)

        src_idx = rows_idx[r_src, c_src].ravel()
        dst_idx = rows_idx[r_dst, c_dst].ravel()

        # Keep only arcs where both source and destination are passable
        mask = passable[src_idx] & passable[dst_idx]
        src_ok = src_idx[mask]
        dst_ok = dst_idx[mask]
        weights = flat[dst_ok] * wf

        rows_list.append(src_ok)
        cols_list.append(dst_ok)
        data_list.append(weights)

    all_rows = np.concatenate(rows_list)
    all_cols = np.concatenate(cols_list)
    all_data = np.concatenate(data_list)

    return scipy.sparse.csr_matrix((all_data, (all_rows, all_cols)), shape=(n, n), dtype=np.float64)


MAX_FIELD_CELLS = 1_000_000
"""Au-delà, le champ est calculé sur une grille agrégée (Jezero : 2 500 × 2 500 cases à 2 m,
soit plus de 7 s et plusieurs Go pour le graphe ; agrégé à 6 m, environ 1 s). Le temps de
retour sert aux budgets et au point de non-retour : une maille de 6 m suffit."""


def _coarsen_cost(cost: np.ndarray, k: int) -> np.ndarray:
    """Coût d'une case agrégée k × k : k fois la moyenne des cases franchissables, inf si
    aucune ne l'est (une case de k fois la taille prend k fois plus de temps à traverser)."""
    height, width = cost.shape
    h, w = -(-height // k), -(-width // k)
    padded = np.full((h * k, w * k), np.inf, dtype=np.float64)
    padded[:height, :width] = cost
    blocks = padded.reshape(h, k, w, k)
    finite = np.isfinite(blocks)
    n = finite.sum(axis=(1, 3))
    total = np.where(finite, blocks, 0.0).sum(axis=(1, 3))
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(n > 0, k * total / np.maximum(n, 1), np.inf)
    return out


def return_field(cost_grid: CostGrid, habitat: LonLat, suit: SuitModel) -> ReturnField:
    """Temps de retour le plus court vers l'habitat depuis chaque case (en secondes).

    Utilise scipy.sparse.csgraph.shortest_path (Dijkstra) sur la grille de coût.
    ``suit`` est accepté pour compatibilité de signature mais non utilisé :
    le temps de retour est en secondes de coût, cohérent avec la grille.
    """
    site = cost_grid.site
    cost = cost_grid.cost  # shape (height, width)
    height, width = cost.shape

    # Coordonnées de l'habitat en mètres → case la plus proche
    hx, hy = to_analysis(site, habitat[0], habitat[1])
    h_cell = site.xy_to_cell(hx, hy)

    if h_cell is None:
        # Habitat hors grille : repli distance euclidienne à 1 m/s
        a, _, c, _, e, f = cost_grid.transform
        xs = c + a * (np.arange(width) + 0.5)
        ys = f + e * (np.arange(height) + 0.5)
        dist = np.hypot(xs[None, :] - hx, ys[:, None] - hy).astype(np.float32)
        return ReturnField(
            site=site,
            transform=cost_grid.transform,
            resolution_m=cost_grid.resolution_m,
            seconds=dist,
            habitat=LonLat(*habitat),
        )

    h_row, h_col = h_cell
    k = max(1, math.ceil(math.sqrt(height * width / MAX_FIELD_CELLS)))
    work = _coarsen_cost(np.asarray(cost, dtype=np.float64), k) if k > 1 else cost
    w_width = work.shape[1]
    source_node = (h_row // k) * w_width + (h_col // k)

    graph = _build_graph(work)

    # Dijkstra depuis le nœud source (direction : habitat → reste de la grille)
    # On veut le temps de retour de chaque case vers l'habitat, soit la distance
    # du graphe transposé depuis l'habitat.  scipy permet de passer directed=True
    # et de fournir le graphe transposé.
    dist_array = scipy.sparse.csgraph.dijkstra(
        graph.T,  # transposé : arcs inversés → distance vers l'habitat
        directed=True,
        indices=source_node,
        return_predecessors=False,
    )

    seconds = dist_array.reshape(work.shape).astype(np.float32)
    if k > 1:
        seconds = np.repeat(np.repeat(seconds, k, axis=0), k, axis=1)[:height, :width]

    return ReturnField(
        site=site,
        transform=cost_grid.transform,
        resolution_m=cost_grid.resolution_m,
        seconds=seconds,
        habitat=LonLat(*habitat),
    )


def return_time_at(field: ReturnField, lon: float, lat: float) -> float | None:
    """Temps de retour au point (lon, lat), ou None hors grille ou inaccessible."""
    from marswalk_core.geodesy import to_analysis as _ta

    x, y = _ta(field.site, lon, lat)
    cell = field.site.xy_to_cell(x, y)
    if cell is None:
        return None
    val = float(field.seconds[cell])
    return None if math.isinf(val) or math.isnan(val) else val
