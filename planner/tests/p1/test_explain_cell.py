"""Tests P1-G : explication du coût d'une cellule.

Vérifications :
- Les termes retournés sont cohérents avec le coût réel.
- Les cellules interdites retournent un seul terme 'forbidden'.
- Les poids négatifs (science) sont correctement représentés.
- Les pénalités actives apparaissent dans les raisons.
- Hors grille → liste vide.
"""

from __future__ import annotations

import numpy as np
import pytest

from marswalk_core.schemas import SafetySettings
from marswalk_planner.cost import build_cost_grid, explain_cell

from .conftest import GRID_SIZE, make_layers, make_site


def _center_xy(site) -> tuple[float, float]:
    """Coordonnées du centre de la grille en mètres."""
    return 0.0, 0.0


def _cell_xy(site, row: int, col: int) -> tuple[float, float]:
    """Coordonnées du centre de la cellule (row, col) en mètres."""
    a, _b, cx, _d, e, f = site.transform
    x = cx + a * (col + 0.5)
    y = f + e * (row + 0.5)
    return float(x), float(y)


# ---------------------------------------------------------------------------
# Cellule interdite
# ---------------------------------------------------------------------------


def test_explain_forbidden_returns_one_term(standard_settings: SafetySettings) -> None:
    """Cellule interdite → un seul terme 'forbidden'."""
    layers = make_layers(slope_val=25.0)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    x, y = _cell_xy(site, 0, 0)
    terms = explain_cell(grid, x, y)
    assert len(terms) == 1
    assert terms[0].name == "forbidden"
    assert np.isinf(terms[0].value)


def test_explain_forbidden_mentions_cause(standard_settings: SafetySettings) -> None:
    """La raison de la cellule interdite mentionne la cause."""
    layers = make_layers(slope_val=25.0)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    x, y = _cell_xy(site, 0, 0)
    terms = explain_cell(grid, x, y)
    assert "pente" in terms[0].reason.lower() or "slope" in terms[0].reason.lower(), (
        f"La raison ne mentionne pas la pente : {terms[0].reason}"
    )


def test_explain_forbidden_obstacle(standard_settings: SafetySettings) -> None:
    """Cellule obstacle interdite → raison mentionne 'obstacle'."""
    layers = make_layers(has_obstacle=True)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    # Trouver une cellule obstacle (quart inférieur-gauche)
    quarter = GRID_SIZE // 2
    row, col = quarter // 2, quarter // 2
    x, y = _cell_xy(site, row, col)
    terms = explain_cell(grid, x, y)
    assert terms[0].name == "forbidden"
    assert "obstacle" in terms[0].reason.lower()


# ---------------------------------------------------------------------------
# Cellule non interdite
# ---------------------------------------------------------------------------


def test_explain_non_forbidden_has_time_risk_science(standard_settings: SafetySettings) -> None:
    """Cellule libre → termes time, risk, science."""
    layers = make_layers(slope_val=5.0)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    x, y = _cell_xy(site, 0, 0)
    terms = explain_cell(grid, x, y)
    names = {t.name for t in terms}
    assert "time" in names
    assert "risk" in names
    assert "science" in names


def test_explain_reconstruction_matches_cost(standard_settings: SafetySettings) -> None:
    """w_t·t + w_r·R − w_s·S = coût réel (à 1 e-3 près)."""
    layers = make_layers(slope_val=5.0)
    layers["crism_minerals"][:] = 1.0  # S = 0.5
    layers["radio_coverage"][:] = 0.0  # pénalité radio
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)

    for row, col in [(0, 0), (10, 10), (50, 50)]:
        x, y = _cell_xy(site, row, col)
        if grid.forbidden[row, col]:
            continue
        terms = explain_cell(grid, x, y)
        actual = float(grid.cost[row, col])
        reconstructed = max(sum(t.value * t.weight for t in terms if t.name != "_debug"), 0.0)
        assert abs(reconstructed - actual) < 1e-3, (
            f"({row},{col}) reconstruit={reconstructed:.5f} réel={actual:.5f}"
        )


def test_explain_science_weight_is_negative(standard_settings: SafetySettings) -> None:
    """Le terme science a un poids négatif (c'est un bonus)."""
    layers = make_layers(slope_val=5.0)
    layers["crism_minerals"][:] = 2.0
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    x, y = _cell_xy(site, 0, 0)
    terms = explain_cell(grid, x, y)
    sci = next(t for t in terms if t.name == "science")
    assert sci.weight < 0, f"Le poids science doit être négatif : {sci.weight}"


def test_explain_active_penalty_appears_in_reason(standard_settings: SafetySettings) -> None:
    """La pénalité radio active apparaît dans la raison du terme risque."""
    layers = make_layers(radio=0.0)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    x, y = _cell_xy(site, 0, 0)
    terms = explain_cell(grid, x, y)
    risk_term = next(t for t in terms if t.name == "risk")
    assert "radio" in risk_term.reason.lower(), (
        f"La raison du risque ne mentionne pas 'radio' : {risk_term.reason}"
    )


def test_explain_no_active_penalty_when_nominal(standard_settings: SafetySettings) -> None:
    """Cellule nominale (pente 0°, radio=1, illum=0.5) → R=0 et aucune pénalité."""
    layers = make_layers(slope_val=0.0, radio=1.0, illumination=0.5)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    x, y = _cell_xy(site, 0, 0)
    terms = explain_cell(grid, x, y)
    risk_term = next(t for t in terms if t.name == "risk")
    assert risk_term.value == pytest.approx(0.0, abs=1e-5), (
        f"R={risk_term.value} doit être 0 pour une cellule nominale"
    )


# ---------------------------------------------------------------------------
# Hors grille
# ---------------------------------------------------------------------------


def test_explain_out_of_bounds_returns_empty(standard_settings: SafetySettings) -> None:
    """Coordonnées hors grille → liste vide."""
    layers = make_layers()
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    # Coordonnée très loin hors de la grille
    terms = explain_cell(grid, 1e9, 1e9)
    assert terms == []


# ---------------------------------------------------------------------------
# Cohérence avec le site fictif
# ---------------------------------------------------------------------------


def test_explain_fictif_site_coherent(fictif_site, standard_settings: SafetySettings) -> None:
    """Sur le site fictif, explain_cell est cohérent sur 50 cellules finies."""
    grid = build_cost_grid(fictif_site, standard_settings)
    fin_idx = np.argwhere(np.isfinite(grid.cost))

    # Échantillonner 50 cellules réparties
    step = max(1, len(fin_idx) // 50)
    sample = fin_idx[::step][:50]

    a, _b, cx, _d, e, f = fictif_site.transform
    for row, col in sample:
        x = cx + a * (col + 0.5)
        y = f + e * (row + 0.5)
        terms = explain_cell(grid, float(x), float(y))
        actual = float(grid.cost[row, col])
        reconstructed = max(sum(t.value * t.weight for t in terms if t.name != "_debug"), 0.0)
        assert abs(reconstructed - actual) < 1e-2, (
            f"({row},{col}) reconstruit={reconstructed:.5f} réel={actual:.5f}"
        )
