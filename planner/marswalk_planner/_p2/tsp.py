"""Optimisation de l'ordre des cibles (TSP).

Deux modes selon le nombre de cibles :
- ≤ 8 cibles : résolution exacte par permutation exhaustive (n! au plus 40 320).
  Utilise la matrice de coûts réels (chemin A*) entre toutes les paires.
- > 8 cibles : heuristique « plus proche voisin » (nearest-neighbor greedy),
  aussi dite NN-TSP, avec un redémarrage depuis chaque nœud de départ et
  sélection du meilleur résultat.

Dans les deux cas, le coût entre deux points est estimé via la distance
euclidienne pondérée par le coût moyen de la grille sur le segment direct
(approximation rapide) si le nombre de paires est grand, ou via un A*
complet si les paires sont peu nombreuses (≤ 8+1 nœuds = 36 paires max).

L'ordre du départ est fixe (l'astronaute part toujours de ``start``).
La destination finale est toujours ``end`` (retour à l'habitat).

Référence :
  Christofides, N. (1976). Worst-case analysis of a new heuristic for the
  travelling salesman problem. (Heuristique NN ici, pas Christofides.)
  Applegate, D.L. et al. (2006). The Traveling Salesman Problem.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable

from marswalk_core.geodesy import to_analysis
from marswalk_core.grids import CostGrid
from marswalk_core.schemas import LonLat, Target

# Seuil exact/heuristique
EXACT_MAX = 8


def _euclid_cost(cost_grid: CostGrid, a: LonLat, b: LonLat) -> float:
    """Estimation rapide du coût de déplacement : distance euclidienne
    en cases × coût moyen non infini de la grille.

    Utilisé pour la matrice de paires dans la heuristique NN.
    N'est pas le coût réel, mais une bonne approximation pour l'ordre.
    """
    import numpy as np

    ax, ay = to_analysis(cost_grid.site, a.lon, a.lat)
    bx, by = to_analysis(cost_grid.site, b.lon, b.lat)
    dist_m = math.hypot(bx - ax, by - ay)

    finite = cost_grid.cost[np.isfinite(cost_grid.cost)]
    mean_cost = float(np.mean(finite)) if len(finite) > 0 else 1.0
    return dist_m / cost_grid.resolution_m * mean_cost


def _build_cost_matrix(
    cost_grid: CostGrid,
    nodes: list[LonLat],
    cost_fn: Callable[[LonLat, LonLat], float],
) -> list[list[float]]:
    n = len(nodes)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = cost_fn(nodes[i], nodes[j])
            matrix[i][j] = c
            matrix[j][i] = c
    return matrix


def _total_cost(order: list[int], matrix: list[list[float]], start_idx: int, end_idx: int) -> float:
    """Coût total du chemin start → order[0] → ... → order[-1] → end."""
    if not order:
        return matrix[start_idx][end_idx]
    total = matrix[start_idx][order[0]]
    for k in range(len(order) - 1):
        total += matrix[order[k]][order[k + 1]]
    total += matrix[order[-1]][end_idx]
    return total


def _exact_tsp(
    matrix: list[list[float]],
    start_idx: int,
    target_indices: list[int],
    end_idx: int,
) -> list[int]:
    """TSP exact par permutation exhaustive.

    Retourne les indices des cibles dans l'ordre optimal.
    """
    best_order: list[int] = list(target_indices)
    best_cost = _total_cost(best_order, matrix, start_idx, end_idx)

    for perm in itertools.permutations(target_indices):
        c = _total_cost(list(perm), matrix, start_idx, end_idx)
        if c < best_cost:
            best_cost = c
            best_order = list(perm)

    return best_order


def _nn_tsp(
    matrix: list[list[float]],
    start_idx: int,
    target_indices: list[int],
    end_idx: int,
) -> list[int]:
    """Heuristique plus-proche-voisin avec redémarrage depuis chaque cible.

    Retourne l'ordre de visite optimal trouvé parmi tous les redémarrages.
    """
    best_order: list[int] = list(target_indices)
    best_cost = _total_cost(best_order, matrix, start_idx, end_idx)

    # Redémarrage depuis chaque nœud de départ possible (y compris start)
    for init in [start_idx, *list(target_indices)]:
        order = _nn_from(matrix, init, list(target_indices), end_idx)
        c = _total_cost(order, matrix, start_idx, end_idx)
        if c < best_cost:
            best_cost = c
            best_order = order

    return best_order


def _nn_from(
    matrix: list[list[float]],
    start: int,
    to_visit: list[int],
    end_idx: int,
) -> list[int]:
    """Greedy nearest-neighbor depuis ``start``, visite tous les nœuds de ``to_visit``."""
    remaining = list(to_visit)
    current = start
    order: list[int] = []
    while remaining:
        best_next = min(remaining, key=lambda j: matrix[current][j])
        order.append(best_next)
        remaining.remove(best_next)
        current = best_next
    return order


def optimize_order(
    cost_grid: CostGrid,
    start: LonLat,
    targets: list[Target],
    end: LonLat,
) -> list[Target]:
    """Ordonne les cibles pour minimiser le coût total du parcours.

    Paramètres
    ----------
    cost_grid:
        Grille de coût pour l'estimation des distances.
    start:
        Position de départ.
    targets:
        Liste des cibles à ordonner.
    end:
        Point d'arrivée (habitat ou départ).

    Retourne
    --------
    list[Target]
        Cibles dans l'ordre optimal trouvé.
    """
    if len(targets) <= 1:
        return list(targets)

    # Construire la liste de nœuds : start + targets + end
    # start_idx = 0, targets = 1..n, end_idx = n+1
    nodes: list[LonLat] = [start, *[t.position for t in targets], end]
    n_targets = len(targets)
    start_idx = 0
    end_idx = n_targets + 1
    target_indices = list(range(1, n_targets + 1))

    def cost_fn(a: LonLat, b: LonLat) -> float:
        return _euclid_cost(cost_grid, a, b)

    matrix = _build_cost_matrix(cost_grid, nodes, cost_fn)

    if n_targets <= EXACT_MAX:
        ordered_indices = _exact_tsp(matrix, start_idx, target_indices, end_idx)
    else:
        ordered_indices = _nn_tsp(matrix, start_idx, target_indices, end_idx)

    # Convertir les indices en cibles
    idx_to_target = {i + 1: t for i, t in enumerate(targets)}
    return [idx_to_target[i] for i in ordered_indices]
