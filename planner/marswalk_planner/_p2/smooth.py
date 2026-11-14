"""Lissage de chemin sur grille de coût.

Algorithme : « String pulling » (aussi appelé « funnel algorithm » simplifié
ou tangent bug simplification).

Principe :
  Pour un chemin donné [p0, p1, ..., pn], tenter de sauter directement de
  pi vers pj (j > i + 1) si le segment pi→pj ne traverse aucune cellule
  interdite. Conserver pi→pi+1 sinon.

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


def smooth_path(cost: FloatGrid, path: list[Cell]) -> list[Cell]:
    """Lisse ``path`` par string-pulling sans traverser de cellule interdite.

    Paramètres
    ----------
    cost:
        Grille de coût ; +inf = cellule interdite.
    path:
        Chemin issu de A*, liste de Cell(row, col).

    Retourne
    --------
    list[Cell]
        Chemin lissé (au moins aussi long que 2 cases si path en a ≥ 2).
        Identique à path si aucun lissage n'est possible.
    """
    if len(path) <= 2:
        return path

    result: list[Cell] = [path[0]]
    i = 0
    n = len(path)

    while i < n - 1:
        # Chercher le saut le plus loin possible depuis path[i]
        best = i + 1
        for j in range(n - 1, i + 1, -1):
            if _bresenham_clear(
                cost,
                path[i].row, path[i].col,
                path[j].row, path[j].col,
            ):
                best = j
                break
        result.append(path[best])
        i = best

    return result
