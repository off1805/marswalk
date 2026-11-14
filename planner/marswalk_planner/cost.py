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

from marswalk_core.grids import CostGrid, CostTerm
from marswalk_core.schemas import Conditions, SafetySettings
from marswalk_core.site_package import Site

from marswalk_planner._p1.cost import compute_cost_grid
from marswalk_planner._p1.explain import explain_cell as _explain_cell
from marswalk_planner._p1.layers import load_layers


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
    layers = load_layers(site)
    return compute_cost_grid(layers, settings, site, conditions)


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
