"""Lissage de chemin sur grille de coût.

Algorithme : « String pulling » (aussi appelé « funnel algorithm » simplifié
ou tangent bug simplification).

Principe :
  Pour un chemin donné [p0, p1, ..., pn], tenter de sauter directement de
  pi vers pj (j > i + 1) si le segment pi→pj ne touche aucune cellule
  interdite et ne coûte pas plus cher que le chemin brut pi→…→pj.
  Conserver pi→pi+1 sinon.

Vérification de segment (Bresenham discret) :
  Chaque pixel du segment est testé ; il ne suffit pas de vérifier les
  extrémités. La règle de décision utilise une sous-grille (antialiasing
  conservatif) : si le segment effleure une cellule interdite selon la
  règle de Bresenham à 8-connexité, le segment est rejeté.

Garanties :
  - Aucun point du tracé lissé ne traverse une cellule interdite.
  - Le tracé reste dans l'emprise de la grille.
  - Si le lissage échoue pour un tronçon, le tracé brut est conservé.

Référence :
  Lozano-Pérez, T. & Wesley, M.A. (1979). An algorithm for planning
  collision-free paths among polyhedral obstacles.
  Stout, Q.F. (1987). Supporting division trees for X3T10 media.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from marswalk_planner._p2.astar import Cell

FloatGrid = NDArray[np.float32]


def _bresenham_clear(
    cost: FloatGrid,
    r0: int,
    c0: int,
    r1: int,
    c1: int,
) -> bool:
    """Vérifie que le segment discret (r0,c0)→(r1,c1) ne traverse aucune cellule infinie.

    Utilise l'algorithme de Bresenham à 8-connexité.  Chaque cellule visitée
    est vérifiée ; les cellules hors de la grille sont considérées interdites.
    """
    h, w = cost.shape
    dr = abs(r1 - r0)
    dc = abs(c1 - c0)
    sr = 1 if r1 > r0 else -1
    sc = 1 if c1 > c0 else -1
    r, c = r0, c0
    err = dr - dc

    while True:
        if not (0 <= r < h and 0 <= c < w):
            return False
        if math.isinf(cost[r, c]):
            return False
        if r == r1 and c == c1:
            break
        e2 = 2 * err
        if e2 > -dc:
            err -= dc
            r += sr
        if e2 < dr:
            err += dr
            c += sc

    return True


def _line_cells(
    r0: int, c0: int, r1: int, c1: int
) -> tuple[NDArray[np.intp], NDArray[np.intp], NDArray[np.float64]]:
    """Cases traversées par le segment (r0,c0)→(r1,c1) et longueur parcourue dans chacune.

    Traversée exacte (« supercover ») : toute case que le segment touche, même par un
    coin, est retenue. Les centres de case sont aux coordonnées entières, les bords aux
    demi-entiers. Longueurs en cases (multiplier par la résolution pour des mètres).
    """
    dr = float(r1 - r0)
    dc = float(c1 - c0)
    length = math.hypot(dr, dc)
    if length == 0.0:
        return (
            np.array([r0], dtype=np.intp),
            np.array([c0], dtype=np.intp),
            np.array([0.0]),
        )
    ts = [np.array([0.0, 1.0])]
    if dc != 0.0:
        lo, hi = sorted((c0, c1))
        ts.append(((np.arange(lo, hi) + 0.5) - c0) / dc)
    if dr != 0.0:
        lo, hi = sorted((r0, r1))
        ts.append(((np.arange(lo, hi) + 0.5) - r0) / dr)
    t = np.unique(np.clip(np.concatenate(ts), 0.0, 1.0))
    mid = (t[:-1] + t[1:]) / 2.0
    rows = np.floor(r0 + mid * dr + 0.5).astype(np.intp)
    cols = np.floor(c0 + mid * dc + 0.5).astype(np.intp)
    return rows, cols, np.diff(t) * length


def _line_cost(cost: FloatGrid, a: Cell, b: Cell) -> float:
    """Intégrale du coût le long du segment a→b (``inf`` s'il touche une case interdite
    ou sort de la grille)."""
    h, w = cost.shape
    rows, cols, lengths = _line_cells(a.row, a.col, b.row, b.col)
    if rows.min() < 0 or cols.min() < 0 or rows.max() >= h or cols.max() >= w:
        return math.inf
    values = cost[rows, cols].astype(np.float64)
    if not np.all(np.isfinite(values)):
        return math.inf
    if not _corners_clear(cost, a, b):
        return math.inf
    return float(np.dot(values, lengths))


def _corners_clear(cost: FloatGrid, a: Cell, b: Cell) -> bool:
    """Vrai si le segment ne passe par aucun coin d'une case interdite.

    Un segment qui passe exactement par un coin ne traverse pas les deux cases qui s'y
    touchent en diagonale, mais un point échantillonné à ce coin peut tomber dans l'une
    d'elles : on les exige libres, comme ``astar`` qui ne coupe aucun coin.
    """
    dr = b.row - a.row
    dc = b.col - a.col
    g = math.gcd(abs(dr), abs(dc))
    if dr == 0 or dc == 0 or g == 0:
        return True
    sr, sc = dr // g, dc // g
    if abs(sr) % 2 == 0 or abs(sc) % 2 == 0:
        return True  # le segment ne passe jamais par un coin
    # Coins aux points a + (k + 1/2)·(sr, sc), k = 0…g-1 : on vérifie les quatre cases
    # qui s'y touchent (deux sont déjà sur le segment).
    h, w = cost.shape
    for k in range(g):
        corner_r = a.row + (k + 0.5) * sr
        corner_c = a.col + (k + 0.5) * sc
        for rr in (math.floor(corner_r), math.ceil(corner_r)):
            for cc in (math.floor(corner_c), math.ceil(corner_c)):
                if not (0 <= rr < h and 0 <= cc < w) or math.isinf(float(cost[rr, cc])):
                    return False
    return True


def _path_prefix_cost(cost: FloatGrid, path: list[Cell]) -> NDArray[np.float64]:
    """Coût cumulé le long du chemin brut, même règle que le graphe de ``astar`` :
    pas × (c_a + c_b) / 2."""
    arr = np.array(path, dtype=np.intp)
    vals = cost[arr[:, 0], arr[:, 1]].astype(np.float64)
    steps = np.hypot(*np.diff(arr, axis=0).T.astype(np.float64))
    edge = steps * (vals[:-1] + vals[1:]) / 2.0
    return np.concatenate([[0.0], np.cumsum(edge)])


# Un raccourci est retenu s'il ne coûte pas plus que le chemin brut qu'il remplace (à
# 1 % près). Sans cette règle, le lissage ne regardait que les cases interdites et
# redressait tous les détours par le coût : les trois variantes, qui ne diffèrent que
# par leurs poids, retombaient sur la même ligne droite (écart E5).
_COST_TOLERANCE = 0.01


def smooth_path(cost: FloatGrid, path: list[Cell]) -> list[Cell]:
    """Lisse ``path`` par string-pulling, sans traverser de case interdite ni renchérir
    le tracé.

    Depuis chaque point retenu, on garde le point le plus lointain joignable en ligne
    droite à condition que (1) le segment ne touche aucune case interdite, y compris
    par un coin, et (2) son coût intégré ne dépasse pas celui du chemin brut entre ces
    deux points. Les détours voulus par la grille de coût (pente intermédiaire, sol
    meuble, zone scientifique) sont donc conservés.

    Paramètres
    ----------
    cost:
        Grille de coût ; +inf = cellule interdite.
    path:
        Chemin issu de A*, liste de Cell(row, col).

    Retourne
    --------
    list[Cell]
        Chemin lissé, sous-suite de ``path`` qui en garde les extrémités.
    """
    if len(path) <= 2:
        return path

    prefix = _path_prefix_cost(cost, path)
    n = len(path)
    result: list[Cell] = [path[0]]
    i = 0

    def ok(i: int, j: int) -> bool:
        budget = float(prefix[j] - prefix[i]) * (1.0 + _COST_TOLERANCE) + 1e-9
        return _line_cost(cost, path[i], path[j]) <= budget

    while i < n - 1:
        # Recherche galopante puis dichotomique du point le plus lointain accepté :
        # O(log n) segments testés par sommet retenu (sur Jezero, des milliers de cases
        # par tronçon). Le coût d'une corde n'est pas monotone, le point retenu peut ne
        # pas être le plus lointain possible ; il respecte toujours les deux règles.
        best = i + 1
        step = 1
        bad = n
        while best + step < n:
            j = best + step
            if ok(i, j):
                best = j
                step *= 2
            else:
                bad = j
                break
        lo, hi = best, min(bad, n)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ok(i, mid):
                lo = mid
            else:
                hi = mid
        best = lo
        result.append(path[best])
        i = best

    return result
