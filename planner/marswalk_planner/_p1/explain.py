"""Explication détaillée du coût d'une cellule (P1-G).

``explain_cell(cost_grid, x, y)`` retourne une liste ordonnée de ``CostTerm``,
chaque terme représentant une composante du coût total avec son poids et la
raison humaine associée.

Les termes sont cohérents avec le coût réellement calculé dans ``_p1.cost`` :
  - term.value × term.weight correspond à la contribution au coût total
  - pour S, weight = -w_s (contribution négative = bonus)
  - hors cellule interdite : w_t·t + w_r·R − w_s·S ≈ cost_grid.cost[cell]

Cellule interdite : un seul terme ``CostTerm("forbidden", inf, 1.0, raison)`` est
retourné ; les raisons indiquent quelle règle s'est déclenchée.

Convention de stockage des poids dans ``CostGrid.terms`` :
  "_w_t" → scalaire float (poids temps)
  "_w_r" → scalaire float (poids risque)
  "_w_s" → scalaire float (poids science)
Ces clés sont écrites par ``_p1.cost.compute_cost_grid`` et lues ici.
"""

from __future__ import annotations

import numpy as np

from marswalk_core.grids import CostGrid, CostTerm

_FORBIDDEN_CAUSE_LABELS: dict[str, str] = {
    "cause_slope_forbidden": "pente ≥ seuil",
    "cause_obstacle": "obstacle détecté",
    "cause_dune": "dune active",
    "cause_scarp": "bord de falaise (tampon de sécurité)",
}

_PENALIZED_CAUSE_LABELS: dict[str, str] = {
    "cause_slope_penalized": "pente intermédiaire",
    "cause_loose_soil": "sol meuble",
    "cause_no_radio": "hors couverture radio",
    "cause_shadow": "zone ombragée",
    "cause_roughness": "rugosité élevée",
}


def _get_weight(terms: dict, key: str, default: float) -> float:
    """Lit un scalaire de poids depuis le dict terms (peut être float ou ndarray)."""
    val = terms.get(key, default)
    if isinstance(val, np.ndarray):
        return float(val.flat[0])
    return float(val)


def explain_cell(cost_grid: CostGrid, x: float, y: float) -> list[CostTerm]:
    """Décompose le coût de la cellule en (x, y) mètres en termes individuels.

    Parameters
    ----------
    cost_grid:
        Grille de coût produite par ``build_cost_grid``.
    x, y:
        Coordonnées en mètres dans le système d'analyse du site (règle R1).

    Returns
    -------
    list[CostTerm]
        Termes dans l'ordre : temps, risque, science.
        Retourne ``[]`` si (x, y) est hors grille.
    """
    cell = cost_grid.site.xy_to_cell(x, y)
    if cell is None:
        return []

    row, col = cell
    terms: list[CostTerm] = []

    # --- cellule interdite -----------------------------------------------
    if bool(cost_grid.forbidden[row, col]):
        active: list[str] = []
        for key, label in _FORBIDDEN_CAUSE_LABELS.items():
            arr = cost_grid.terms.get(key)
            if arr is not None and bool(arr[row, col]):
                active.append(label)

        reason = (
            "case interdite : " + ", ".join(active)
            if active
            else "case interdite (raison indéterminée)"
        )
        return [CostTerm(name="forbidden", value=float("inf"), weight=1.0, reason=reason)]

    # --- poids -----------------------------------------------------------
    w_t = _get_weight(cost_grid.terms, "_w_t", 1.0)
    w_r = _get_weight(cost_grid.terms, "_w_r", 1.0)
    w_s = _get_weight(cost_grid.terms, "_w_s", 0.5)

    # --- valeurs des composantes -----------------------------------------
    t_arr = cost_grid.terms.get("time")
    R_arr = cost_grid.terms.get("risk")
    S_arr = cost_grid.terms.get("science")

    t_val = float(t_arr[row, col]) if t_arr is not None else 0.0
    R_val = float(R_arr[row, col]) if R_arr is not None else 0.0
    S_val = float(S_arr[row, col]) if S_arr is not None else 0.0

    # --- terme temporel --------------------------------------------------
    terms.append(CostTerm(
        name="time",
        value=t_val,
        weight=w_t,
        reason=(
            f"temps de traversée {t_val:.2f} s "
            f"(Tobler 0,38 g × facteur sol) → contribution {w_t * t_val:.3f}"
        ),
    ))

    # --- terme de risque -------------------------------------------------
    pen_active: list[str] = []
    for key, label in _PENALIZED_CAUSE_LABELS.items():
        arr = cost_grid.terms.get(key)
        if arr is not None and bool(arr[row, col]):
            pen_active.append(label)

    risk_reason = (
        f"R={R_val:.3f} [{', '.join(pen_active)}] → contribution {w_r * R_val:.3f}"
        if pen_active
        else f"R={R_val:.3f} (aucune pénalité active) → contribution {w_r * R_val:.3f}"
    )
    terms.append(CostTerm(name="risk", value=R_val, weight=w_r, reason=risk_reason))

    # --- terme scientifique (réduction) ----------------------------------
    if S_val > 0.0:
        sci_reason = (
            f"S={S_val:.2f} (minéralogie CRISM) → réduction −{w_s * S_val:.3f}"
        )
    else:
        sci_reason = "S=0 (aucune signature minéralogique détectée)"
    terms.append(CostTerm(name="science", value=S_val, weight=-w_s, reason=sci_reason))

    return terms
