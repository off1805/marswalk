"""Tests P1-D : grille de coût, formule C = w_t·t + w_r·R − w_s·S, poids, NaN.

Vérifications :
- Forme, dtype, valeurs finies / inf correctes.
- Cohérence de la formule sur chaque cellule.
- Modifier les poids change les coûts.
- Les cellules interdites restent +inf quels que soient les poids.
- Les conditions environnementales augmentent R.
- S réduit le coût sans jamais le rendre négatif.
- Pas de NaN dans la grille finale.
"""

from __future__ import annotations

import datetime

import numpy as np

from marswalk_core.schemas import (
    Conditions,
    SafetySettings,
)
from marswalk_planner.cost import build_cost_grid

from .conftest import GRID_SIZE, make_layers, make_site

# ---------------------------------------------------------------------------
# Forme et dtype
# ---------------------------------------------------------------------------


def test_cost_grid_shape(standard_settings: SafetySettings) -> None:
    """La grille a la forme (height, width) du site."""
    layers = make_layers()
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    assert grid.cost.shape == (GRID_SIZE, GRID_SIZE)
    assert grid.forbidden.shape == (GRID_SIZE, GRID_SIZE)


def test_cost_grid_dtype_float32(standard_settings: SafetySettings) -> None:
    """La grille de coût est en float32."""
    layers = make_layers()
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    assert grid.cost.dtype == np.float32


def test_cost_grid_no_nan(standard_settings: SafetySettings) -> None:
    """Aucune valeur NaN dans la grille de coût."""
    layers = make_layers()
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    assert not np.any(np.isnan(grid.cost)), "La grille de coût ne doit pas contenir de NaN"


def test_cost_grid_resolution_matches_site(standard_settings: SafetySettings) -> None:
    """resolution_m de CostGrid correspond à celle du site."""
    layers = make_layers()
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    assert grid.resolution_m == site.manifest.grid.resolution_m


# ---------------------------------------------------------------------------
# Cellules interdites
# ---------------------------------------------------------------------------


def test_forbidden_cells_are_inf(standard_settings: SafetySettings) -> None:
    """Toutes les cellules interdites ont coût +inf."""
    layers = make_layers(slope_val=25.0)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    assert np.all(np.isinf(grid.cost[grid.forbidden]))


def test_forbidden_mask_matches_inf(standard_settings: SafetySettings) -> None:
    """grid.forbidden est exactement l'ensemble des cellules inf."""
    layers = make_layers(has_obstacle=True, slope_val=5.0)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    # Les cellules inf sont exactement les cellules forbidden
    inf_mask = np.isinf(grid.cost)
    assert np.array_equal(inf_mask, grid.forbidden)


def test_forbidden_cells_cannot_be_passages() -> None:
    """Les cellules interdites restent +inf quels que soient les poids."""
    layers = make_layers(slope_val=25.0)
    site, _ = make_site(layers)
    # Poids très favorables (science max, risque nul)
    settings = SafetySettings(
        max_slope_deg=20.0,
        weights={"time": 0.0, "risk": 0.0, "science": 1000.0},
    )
    grid = build_cost_grid(site, settings)
    assert np.all(np.isinf(grid.cost)), (
        "Cellules interdites doivent rester inf même avec poids science=1000"
    )


# ---------------------------------------------------------------------------
# Cohérence de la formule
# ---------------------------------------------------------------------------


def test_formula_coherence_all_cells(standard_settings: SafetySettings) -> None:
    """C = max(w_t·t + w_r·R − w_s·S, 0) pour toutes les cellules finies."""
    layers = make_layers(slope_val=5.0)
    layers["crism_minerals"][:] = 1.0  # S = 0.5 partout
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)

    t_grid = grid.terms["time"]
    r_grid = grid.terms["risk"]
    s_grid = grid.terms["science"]
    w_t = standard_settings.weights.time
    w_r = standard_settings.weights.risk
    w_s = standard_settings.weights.science

    expected = np.maximum(w_t * t_grid + w_r * r_grid - w_s * s_grid, 0.0)
    finite = ~grid.forbidden
    np.testing.assert_allclose(
        grid.cost[finite],
        expected[finite],
        rtol=1e-4,
        err_msg="La formule C = w_t·t + w_r·R − w_s·S n'est pas cohérente",
    )


def test_cost_non_negative(standard_settings: SafetySettings) -> None:
    """Le coût des cellules finies est toujours ≥ 0."""
    layers = make_layers(slope_val=5.0)
    layers["crism_minerals"][:] = 2.0  # S = 1.0 (bonus maximum)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    finite_costs = grid.cost[~grid.forbidden]
    assert float(finite_costs.min()) >= 0.0, "Coût négatif détecté"


# ---------------------------------------------------------------------------
# Effet des poids
# ---------------------------------------------------------------------------


def test_changing_time_weight_changes_cost() -> None:
    """Un poids temps plus élevé augmente le coût des cellules finies."""
    layers = make_layers(slope_val=5.0)
    site, _ = make_site(layers)

    s_low = SafetySettings(weights={"time": 0.5, "risk": 1.0, "science": 0.5})
    s_high = SafetySettings(weights={"time": 2.0, "risk": 1.0, "science": 0.5})

    grid_low = build_cost_grid(site, s_low)
    grid_high = build_cost_grid(site, s_high)

    cost_low = float(grid_low.cost[0, 0])
    cost_high = float(grid_high.cost[0, 0])
    assert cost_high > cost_low, (
        f"w_t=2.0 ({cost_high}) doit donner un coût plus élevé que w_t=0.5 ({cost_low})"
    )


def test_changing_science_weight_changes_cost() -> None:
    """Un poids science plus élevé réduit le coût des cellules avec CRISM."""
    layers = make_layers(slope_val=5.0)
    layers["crism_minerals"][:] = 2.0  # olivine, S=1.0
    site, _ = make_site(layers)

    s_low = SafetySettings(weights={"time": 1.0, "risk": 1.0, "science": 0.1})
    s_high = SafetySettings(weights={"time": 1.0, "risk": 1.0, "science": 0.8})

    grid_low = build_cost_grid(site, s_low)
    grid_high = build_cost_grid(site, s_high)

    cost_low = float(grid_low.cost[0, 0])
    cost_high = float(grid_high.cost[0, 0])
    assert cost_high < cost_low, (
        f"w_s=0.8 ({cost_high}) doit donner un coût plus bas que w_s=0.1 ({cost_low})"
    )


def test_changing_risk_weight_changes_cost() -> None:
    """Un poids risque plus élevé amplifie l'effet de R."""
    layers = make_layers(radio=0.0)  # R > 0 partout (hors radio)
    site, _ = make_site(layers)

    s_low = SafetySettings(weights={"time": 1.0, "risk": 0.1, "science": 0.5})
    s_high = SafetySettings(weights={"time": 1.0, "risk": 2.0, "science": 0.5})

    grid_low = build_cost_grid(site, s_low)
    grid_high = build_cost_grid(site, s_high)

    cost_low = float(grid_low.cost[0, 0])
    cost_high = float(grid_high.cost[0, 0])
    assert cost_high > cost_low


# ---------------------------------------------------------------------------
# Conditions environnementales
# ---------------------------------------------------------------------------


def test_conditions_dust_increases_risk() -> None:
    """Poussière élevée (tau > max) augmente R."""
    layers = make_layers()
    site, _ = make_site(layers)
    settings = SafetySettings(max_dust_tau=2.0)

    grid_no_dust = build_cost_grid(site, settings, conditions=None)
    cond = Conditions(utc=datetime.datetime(2026, 11, 1), dust_tau=4.0)
    grid_dust = build_cost_grid(site, settings, conditions=cond)

    r_no = float(grid_no_dust.terms["risk"][0, 0])
    r_dust = float(grid_dust.terms["risk"][0, 0])
    assert r_dust > r_no, f"R avec poussière ({r_dust}) doit dépasser R sans ({r_no})"


def test_conditions_dose_rate_increases_risk() -> None:
    """Débit de dose élevé augmente R."""
    layers = make_layers()
    site, _ = make_site(layers)
    settings = SafetySettings(max_dose_usv=1000.0)

    cond = Conditions(
        utc=datetime.datetime(2026, 11, 1),
        dose_rate_usv_h=300.0,  # > 1000/8 = 125
    )
    grid_no = build_cost_grid(site, settings)
    grid_yes = build_cost_grid(site, settings, conditions=cond)

    r_no = float(grid_no.terms["risk"][0, 0])
    r_yes = float(grid_yes.terms["risk"][0, 0])
    assert r_yes > r_no


def test_conditions_nominal_no_effect() -> None:
    """Conditions nominales (en dessous des seuils) ne changent pas R."""
    layers = make_layers()
    site, _ = make_site(layers)
    settings = SafetySettings(max_dust_tau=2.0, max_dose_usv=1000.0)

    cond = Conditions(
        utc=datetime.datetime(2026, 11, 1),
        dust_tau=1.0,  # < max_dust_tau
        dose_rate_usv_h=50.0,  # < 1000/8 = 125
    )
    grid_no = build_cost_grid(site, settings)
    grid_cond = build_cost_grid(site, settings, conditions=cond)

    # R doit être identique
    np.testing.assert_array_equal(grid_no.terms["risk"], grid_cond.terms["risk"])


# ---------------------------------------------------------------------------
# Intérêt scientifique
# ---------------------------------------------------------------------------


def test_science_zero_when_no_crism() -> None:
    """S=0 quand CRISM est absent."""
    layers = make_layers()
    layers["crism_minerals"][:] = 0.0
    site, _ = make_site(layers)
    grid = build_cost_grid(site, SafetySettings())
    assert float(grid.terms["science"].max()) == 0.0


def test_science_half_for_class1() -> None:
    """S=0,5 pour CRISM classe 1 (argiles/carbonates)."""
    layers = make_layers()
    layers["crism_minerals"][:] = 1.0
    site, _ = make_site(layers)
    grid = build_cost_grid(site, SafetySettings())
    np.testing.assert_allclose(grid.terms["science"], 0.5, rtol=1e-5)


def test_science_one_for_class2() -> None:
    """S=1 pour CRISM classe 2 (olivine)."""
    layers = make_layers()
    layers["crism_minerals"][:] = 2.0
    site, _ = make_site(layers)
    grid = build_cost_grid(site, SafetySettings())
    np.testing.assert_allclose(grid.terms["science"], 1.0, rtol=1e-5)


# ---------------------------------------------------------------------------
# Terms dict
# ---------------------------------------------------------------------------


def test_terms_contains_expected_keys(standard_settings: SafetySettings) -> None:
    """CostGrid.terms contient les composantes attendues."""
    layers = make_layers()
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    for key in ("time", "risk", "science", "penalized"):
        assert key in grid.terms, f"Clé absente de grid.terms : {key}"


def test_terms_time_matches_resolution(standard_settings: SafetySettings) -> None:
    """Sur terrain plat, t ≈ resolution / base_speed."""
    layers = make_layers(slope_val=0.0)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    t_flat = float(grid.terms["time"][0, 0])
    # Sur plat, Tobler donne ≈ vitesse max (légèrement descendante → speed > 1)
    # Mais à 0° c'est proche de 1 m/s
    assert 1.5 <= t_flat <= 3.0, f"t sur plat ({t_flat}) hors de la plage attendue [1.5, 3.0]"
