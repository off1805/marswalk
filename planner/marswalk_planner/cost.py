"""Grille de coût (P1).

Signatures gelées (taches-agents.md section 7) :
  ``build_cost_grid(site, settings, conditions) -> CostGrid``
  ``explain_cell(cost_grid, x, y) -> list[CostTerm]``

Formule (section 7, taches-agents.md) :
  C = w_t · t + w_r · R − w_s · S
  où t = temps de traversée (s), R = risque normalisé [0,1], S = intérêt
  scientifique normalisé [0,1], et w_t/w_r/w_s sont les poids de SafetySettings.

Cellules interdites : cost[forbidden] = +inf, identifiables via CostGrid.forbidden.
"""

from __future__ import annotations

import dataclasses
from collections import OrderedDict

from marswalk_core.grids import CostGrid, CostTerm
from marswalk_core.schemas import Conditions, SafetySettings
from marswalk_core.site_package import Site
from marswalk_planner._p1.cost import compute_cost_grid
from marswalk_planner._p1.explain import explain_cell as _explain_cell
from marswalk_planner._p1.layers import load_layers
from marswalk_planner._p1.planning_site import planning_site


def build_cost_grid(
    site: Site,
    settings: SafetySettings,
    conditions: Conditions | None = None,
) -> CostGrid:
    """Construit la grille de coût de déplacement à la résolution du site (2 m).

    Parameters
    ----------
    site:
        Paquet de site ouvert (``load_site`` ou ``open_package``).
    settings:
        Seuils et poids de sécurité (``load_safety_settings``).
    conditions:
        Conditions martiennes instantanées (poussière, débit de dose…).
        ``None`` = conditions nominales.

    Returns
    -------
    CostGrid
        - ``cost``     : tableau float32, +inf sur les cellules interdites.
        - ``forbidden``: masque booléen des cellules inaccessibles.
        - ``terms``    : composantes individuelles (time, risk, science) et
                         masques par cause (cause_slope_forbidden, …).
        - ``warnings`` : avertissements sur les couches manquantes/dégradées.

    Performance
    -----------
    5 × 5 km à 2 m (2500 × 2500) < 1 s sur l'environnement de référence.
    Toutes les opérations sont vectorisées avec NumPy.
    """
    site = planning_site(site)  # grille de 2 m même quand le paquet est à 1 m
    key = (
        id(site),
        settings.model_dump_json(),
        conditions.model_dump_json() if conditions is not None else "",
    )
    grid = _GRID_CACHE.get(key)
    if grid is None:
        layers = load_layers(site)
        grid = compute_cost_grid(layers, settings, site, conditions)
        _GRID_CACHE[key] = grid
        while len(_GRID_CACHE) > _GRID_CACHE_SIZE:
            _GRID_CACHE.popitem(last=False)
    else:
        _GRID_CACHE.move_to_end(key)
    # Copie des tableaux modifiables : l'appelant peut y ajouter un obstacle signalé.
    return dataclasses.replace(
        grid,
        cost=grid.cost.copy(),
        forbidden=grid.forbidden.copy(),
        warnings=list(grid.warnings),
    )


# Grilles déjà construites (sur Jezero, 0,5 s par grille et trois grilles par plan) :
# déplacer une cible ne reconstruit pas les grilles des trois variantes.
_GRID_CACHE: OrderedDict[tuple[int, str, str], CostGrid] = OrderedDict()
_GRID_CACHE_SIZE = 8


def clear_cost_grid_cache() -> None:
    _GRID_CACHE.clear()


def explain_cell(cost_grid: CostGrid, x: float, y: float) -> list[CostTerm]:
    """Décompose le coût de la cellule en (x, y) mètres en termes individuels.

    Parameters
    ----------
    cost_grid:
        Grille produite par ``build_cost_grid``.
    x, y:
        Coordonnées en mètres dans le système d'analyse du site (règle R1).

    Returns
    -------
    list[CostTerm]
        Chaque terme contient :
          - ``name``   : "time", "risk", "science" ou "forbidden"
          - ``value``  : valeur brute de la composante
          - ``weight`` : poids appliqué (négatif pour science)
          - ``reason`` : explication lisible

        Somme des (value × weight) = cost réel de la cellule (hors cas interdit).
        Retourne ``[]`` si (x, y) est hors grille.
    """
    return _explain_cell(cost_grid, x, y)
