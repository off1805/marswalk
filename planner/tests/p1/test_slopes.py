"""Tests P1-B/C/D : règles de pente (9°, 10°, 15°, 20°, 21°).

Hypothèses :
- max_slope_deg = 20° (seuil d'interdiction, standard preset)
- penalty_slope_deg = 10° (seuil de pénalité, standard preset)
- Une cellule à exactement 20° est interdite (borne inclusive).
- Une cellule à 10° est pénalisée mais pas interdite.
- Une cellule à 9° n'est ni interdite ni pénalisée.
"""

from __future__ import annotations

import numpy as np
import pytest

from marswalk_core.schemas import SafetySettings
from marswalk_planner.cost import build_cost_grid, explain_cell
from marswalk_planner.hazards import hazard_masks

from .conftest import make_layers, make_site


def _flat_site(slope_deg: float) -> tuple:
    """Site 100×100 avec pente uniforme ``slope_deg`` partout."""
    layers = make_layers(slope_val=slope_deg)
    return make_site(layers)


@pytest.mark.parametrize(
    "slope_deg, expect_forbidden, expect_penalized",
    [
        (9.0,  False, False),
        (10.0, False, True),
        (15.0, False, True),
        (20.0, True,  False),
        (21.0, True,  False),
    ],
)
def test_slope_classification(
    slope_deg: float,
    expect_forbidden: bool,
    expect_penalized: bool,
    standard_settings: SafetySettings,
) -> None:
    """La règle de pente classe correctement chaque seuil."""
    site, _ = _flat_site(slope_deg)
    masks = hazard_masks(site, standard_settings)

    all_forbidden = bool(masks.forbidden.all())
    all_penalized = bool(masks.penalized.all())

    assert all_forbidden == expect_forbidden, (
        f"slope={slope_deg}° : forbidden={all_forbidden}, attendu={expect_forbidden}"
    )
    if not expect_forbidden:
        # Soit tout est pénalisé, soit rien ne l'est
        assert all_penalized == expect_penalized, (
            f"slope={slope_deg}° : penalized={all_penalized}, attendu={expect_penalized}"
        )


def test_slope_forbidden_and_penalized_are_disjoint(standard_settings: SafetySettings) -> None:
    """Les zones interdites et pénalisées ne se recoupent jamais."""
    layers = make_layers(slope_val=15.0)
    layers["slope"][:50, :] = 25.0  # moitié interdite, moitié pénalisée
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)
    assert not np.any(masks.forbidden & masks.penalized)


def test_slope_forbidden_at_exactly_20deg(standard_settings: SafetySettings) -> None:
    """La borne est inclusive : 20° est interdit."""
    site, _ = _flat_site(20.0)
    masks = hazard_masks(site, standard_settings)
    assert masks.forbidden.all()


def test_slope_penalized_at_exactly_10deg(standard_settings: SafetySettings) -> None:
    """La borne de pénalité est inclusive : 10° est pénalisé."""
    site, _ = _flat_site(10.0)
    masks = hazard_masks(site, standard_settings)
    assert masks.penalized.all()
    assert not masks.forbidden.any()


def test_slope_19_99_not_forbidden(standard_settings: SafetySettings) -> None:
    """19,99° n'est pas interdit."""
    site, _ = _flat_site(19.99)
    masks = hazard_masks(site, standard_settings)
    assert not masks.forbidden.any()
    assert masks.penalized.any()


def test_slope_cost_increases_with_slope(standard_settings: SafetySettings) -> None:
    """Le coût de traversée augmente avec la pente (Tobler)."""
    site_0, _ = _flat_site(0.0)
    site_10, _ = _flat_site(10.0)
    grid_0 = build_cost_grid(site_0, standard_settings)
    grid_10 = build_cost_grid(site_10, standard_settings)

    cost_0 = float(grid_0.cost[0, 0])
    cost_10 = float(grid_10.cost[0, 0])
    assert cost_10 > cost_0, f"Coût 10° ({cost_10}) devrait dépasser coût 0° ({cost_0})"


def test_slope_risk_term_in_intermediate_range(standard_settings: SafetySettings) -> None:
    """Entre 10° et 20°, R > 0 (pénalité de risque active)."""
    site, _ = _flat_site(15.0)
    grid = build_cost_grid(site, standard_settings)
    r_grid = grid.terms["risk"]
    assert float(r_grid[0, 0]) > 0.0


def test_slope_risk_zero_below_penalty(standard_settings: SafetySettings) -> None:
    """Sous le seuil de pénalité, la pente ne contribue pas au risque."""
    site, _ = _flat_site(5.0)
    grid = build_cost_grid(site, standard_settings)
    # La contribution pente au risque est nulle ; le risque total peut être non-nul
    # à cause d'autres couches, mais ici toutes les couches sont à valeur nominale
    # (radio=1, illum=0.5>0, roughness=0.1<0.5) → R doit être zéro
    r_grid = grid.terms["risk"]
    assert float(r_grid[0, 0]) == pytest.approx(0.0, abs=1e-5)


def test_slope_forbidden_causes_inf_cost(standard_settings: SafetySettings) -> None:
    """Les cellules à pente > 20° ont un coût +inf dans la grille."""
    site, _ = _flat_site(25.0)
    grid = build_cost_grid(site, standard_settings)
    assert np.all(np.isinf(grid.cost))


def test_slope_changing_threshold_changes_forbidden_zone() -> None:
    """Modifier max_slope_deg change effectivement les zones interdites."""
    layers = make_layers(slope_val=18.0)
    site, _ = make_site(layers)

    settings_20 = SafetySettings(max_slope_deg=20.0, penalty_slope_deg=10.0)
    settings_15 = SafetySettings(max_slope_deg=15.0, penalty_slope_deg=8.0)

    masks_20 = hazard_masks(site, settings_20)
    masks_15 = hazard_masks(site, settings_15)

    # À 18°, settings_20 → pénalisé ; settings_15 → interdit
    assert not masks_20.forbidden.any(), "18° doit être libre avec seuil 20°"
    assert masks_15.forbidden.all(), "18° doit être interdit avec seuil 15°"


def test_slope_changing_threshold_changes_cost_grid() -> None:
    """Un seuil plus bas donne plus de cellules inf dans la grille de coût."""
    layers = make_layers(slope_val=18.0)
    site, _ = make_site(layers)

    settings_20 = SafetySettings(max_slope_deg=20.0, penalty_slope_deg=10.0)
    settings_15 = SafetySettings(max_slope_deg=15.0, penalty_slope_deg=8.0)

    grid_20 = build_cost_grid(site, settings_20)
    grid_15 = build_cost_grid(site, settings_15)

    inf_20 = int(np.isinf(grid_20.cost).sum())
    inf_15 = int(np.isinf(grid_15.cost).sum())
    assert inf_15 > inf_20, (
        f"Plus de cellules inf avec seuil 15° ({inf_15}) vs 20° ({inf_20})"
    )


def test_explain_cell_slope_forbidden(standard_settings: SafetySettings) -> None:
    """explain_cell sur une cellule interdite par pente renvoie 'forbidden'."""
    site, _ = _flat_site(25.0)
    grid = build_cost_grid(site, standard_settings)
    # Coordonnée au centre
    cx, cy = 0.0, 0.0
    terms = explain_cell(grid, cx, cy)
    assert len(terms) == 1
    assert terms[0].name == "forbidden"
    assert "pente" in terms[0].reason.lower()


def test_explain_cell_non_forbidden_coherent(standard_settings: SafetySettings) -> None:
    """explain_cell : w_t·t + w_r·R − w_s·S = coût réel."""
    site, _ = _flat_site(5.0)
    grid = build_cost_grid(site, standard_settings)
    cx, cy = 0.0, 0.0
    terms = explain_cell(grid, cx, cy)

    actual_cost = float(grid.cost[grid.site.xy_to_cell(cx, cy)])
    reconstructed = sum(t.value * t.weight for t in terms if t.name != "_debug")
    reconstructed = max(reconstructed, 0.0)
    assert abs(reconstructed - actual_cost) < 1e-3, (
        f"Incohérence explain_cell : reconstruit={reconstructed:.4f} réel={actual_cost:.4f}"
    )
