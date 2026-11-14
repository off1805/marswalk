"""Recherche d'itinéraire (P2).

Signature gelée : ``plan_route(cost_grid, waypoints, options) -> RouteGeometry``.

Algorithme : MCP_Geometric (A* sur grille de coût 8-connexité avec lissage
par string-pulling).

La recherche :
- Calcule le chemin de coût minimal entre chaque paire de points de passage.
- Travaille dans une fenêtre spatiale élargie autour du segment direct.
- Agrandit automatiquement la fenêtre si aucun chemin n'est trouvé.
- Respecte les cellules interdites (cost = +inf).
- Lisse le chemin sans traverser d'obstacle.
- Gère les départs/arrivées proches d'obstacles par relocalisation.
"""

from __future__ import annotations

import math

from marswalk_core.geodesy import to_analysis, to_lonlat
from marswalk_core.grids import CostGrid, RouteGeometry, RouteOptions
from marswalk_core.schemas import LonLat
from marswalk_planner._p2 import cache as _cache
from marswalk_planner._p2.astar import Cell, astar_grid
from marswalk_planner._p2.smooth import smooth_path


def _lonlat_to_cell(cost_grid: CostGrid, pt: LonLat) -> Cell | None:
    """Convertit un point LonLat en cellule de grille (row, col)."""
    x, y = to_analysis(cost_grid.site, pt.lon, pt.lat)
    cell = cost_grid.site.xy_to_cell(x, y)
    if cell is None:
        return None
    return Cell(cell[0], cell[1])


def _cell_to_lonlat(cost_grid: CostGrid, cell: Cell) -> LonLat:
    """Convertit une cellule en LonLat (centre de cellule)."""
    a, _, c, _, e, f = cost_grid.transform
    x = c + a * (cell.col + 0.5)
    y = f + e * (cell.row + 0.5)
    lon, lat = to_lonlat(cost_grid.site, x, y)
    return LonLat(lon, lat)


def _window_margin_cells(cost_grid: CostGrid, margin_m: float) -> int:
    """Marge en cases à partir de la marge en mètres."""
    return max(10, math.ceil(margin_m / cost_grid.resolution_m))


def _plan_segment(
    cost_grid: CostGrid,
    start: LonLat,
    end: LonLat,
    options: RouteOptions,
    variant_name: str = "default",
) -> list[LonLat]:
    """Calcule le chemin entre deux points, avec cache.

    Retourne une liste de coordonnées LonLat (incluant start et end).
    Si aucun chemin n'est possible, retourne [start, end] (ligne droite de secours).
    """
    key = _cache.segment_key(cost_grid, start, end, options.window_margin_m, variant_name)
    cached = _cache.get(key)
    if cached is not None:
        return list(cached.coordinates)

    start_cell = _lonlat_to_cell(cost_grid, start)
    end_cell = _lonlat_to_cell(cost_grid, end)

    # Points hors grille : ligne droite de secours
    if start_cell is None or end_cell is None:
        return [start, end]

    margin_cells = _window_margin_cells(cost_grid, options.window_margin_m)

    path_cells = astar_grid(
        cost_grid.cost,
        start_cell,
        end_cell,
        window_margin_cells=margin_cells,
        max_window_expansions=4,
    )

    if path_cells is None:
        # Aucun chemin trouvé → ligne droite (signalée dans warnings)
        result = [start, end]
        _cache.put(key, RouteGeometry(coordinates=result, segment_breaks=[0], cost=float("inf")))
        return result

    # Lissage
    smoothed = smooth_path(cost_grid.cost, path_cells)

    # Conversion en LonLat
    coords: list[LonLat] = []
    for cell in smoothed:
        coords.append(_cell_to_lonlat(cost_grid, cell))

    # Remplacer les extrémités par les coordonnées exactes seulement si elles sont
    # sur des cellules libres. Sinon, conserver les centres de cellule de la recherche.
    if coords:
        import math as _math

        start_cell_check = _lonlat_to_cell(cost_grid, start)
        if start_cell_check is not None and not _math.isinf(
            cost_grid.cost[start_cell_check.row, start_cell_check.col]
        ):
            coords[0] = start
        end_cell_check = _lonlat_to_cell(cost_grid, end)
        if end_cell_check is not None and not _math.isinf(
            cost_grid.cost[end_cell_check.row, end_cell_check.col]
        ):
            coords[-1] = end

    # Coût total du tronçon
    total_cost = 0.0
    for i in range(len(path_cells) - 1):
        r0, c0 = path_cells[i]
        r1, c1 = path_cells[i + 1]
        step_dist = math.hypot(r1 - r0, c1 - c0)
        total_cost += step_dist * (cost_grid.cost[r0, c0] + cost_grid.cost[r1, c1]) / 2.0

    geom = RouteGeometry(coordinates=coords, segment_breaks=[0], cost=total_cost)
    _cache.put(key, geom)
    return coords


def plan_route(
    cost_grid: CostGrid,
    waypoints: list[LonLat],
    options: RouteOptions,
) -> RouteGeometry:
    """Calcule l'itinéraire de coût minimal passant par tous les points de passage.

    Paramètres
    ----------
    cost_grid:
        Grille de coût issue de ``build_cost_grid``.
    waypoints:
        Au moins deux points : [départ, cible_1, ..., cible_n, arrivée].
    options:
        Options de recherche : marge de fenêtre, variante, etc.

    Retourne
    --------
    RouteGeometry
        ``coordinates`` : liste de LonLat du tracé complet.
        ``segment_breaks`` : indices du premier point de chaque tronçon.
        ``cost`` : coût total cumulé.
    """
    if len(waypoints) < 2:
        raise ValueError("Il faut au moins deux points de passage")

    variant_name = options.variant.value if options.variant else "default"

    all_coords: list[LonLat] = []
    segment_breaks: list[int] = []
    total_cost = 0.0

    for i in range(len(waypoints) - 1):
        segment_coords = _plan_segment(
            cost_grid,
            LonLat(*waypoints[i]),
            LonLat(*waypoints[i + 1]),
            options,
            variant_name,
        )
        segment_breaks.append(len(all_coords))
        if i == 0:
            all_coords.extend(segment_coords)
        else:
            # Éviter la duplication du point de jonction
            all_coords.extend(segment_coords[1:])

        # Récupérer le coût depuis le cache
        seg_key = _cache.segment_key(
            cost_grid,
            LonLat(*waypoints[i]),
            LonLat(*waypoints[i + 1]),
            options.window_margin_m,
            variant_name,
        )
        cached_seg = _cache.get(seg_key)
        if cached_seg is not None:
            total_cost += cached_seg.cost

    return RouteGeometry(
        coordinates=all_coords,
        segment_breaks=segment_breaks,
        cost=total_cost,
    )
