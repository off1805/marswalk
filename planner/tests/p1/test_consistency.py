"""Tests P1-F + cohérence masques/polygones/grille.

Vérifications :
- Les polygones couvrent exactement les mêmes zones que les masques.
- Changer un seuil change conjointement masques, polygones ET grille.
- Les causes des polygones correspondent aux causes des masques.
- La grille de coût et les masques partagent exactement les mêmes cellules interdites.
"""

from __future__ import annotations

import numpy as np
import pytest

from marswalk_core.schemas import SafetySettings
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.hazards import hazard_masks, hazard_polygons

from .conftest import GRID_SIZE, make_layers, make_site


# ---------------------------------------------------------------------------
# Cohérence masques ↔ grille de coût
# ---------------------------------------------------------------------------

def test_grid_forbidden_matches_masks_forbidden(standard_settings: SafetySettings) -> None:
    """grid.forbidden == hazard_masks.forbidden (même calcul, appel séparé)."""
    layers = make_layers(slope_val=15.0, has_obstacle=True)
    layers["slope"][:20, :] = 25.0  # zone interdite par pente
    site, _ = make_site(layers)

    masks = hazard_masks(site, standard_settings)
    grid = build_cost_grid(site, standard_settings)

    np.testing.assert_array_equal(
        grid.forbidden, masks.forbidden,
        err_msg="grid.forbidden et hazard_masks.forbidden doivent être identiques"
    )


def test_inf_cells_match_forbidden(standard_settings: SafetySettings) -> None:
    """Les cellules inf dans la grille sont exactement les cellules forbidden."""
    layers = make_layers(slope_val=10.0, has_obstacle=True)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    inf_mask = np.isinf(grid.cost)
    np.testing.assert_array_equal(inf_mask, grid.forbidden)


def test_penalized_cells_not_inf(standard_settings: SafetySettings) -> None:
    """Les cellules pénalisées ont un coût fini (pas +inf)."""
    layers = make_layers(radio=0.0)  # tout pénalisé hors radio
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    penalized = grid.terms["penalized"].astype(bool)
    if penalized.any():
        assert np.all(np.isfinite(grid.cost[penalized])), (
            "Des cellules pénalisées ont un coût infini (elles devraient être finies)"
        )


# ---------------------------------------------------------------------------
# Cohérence masques ↔ polygones
# ---------------------------------------------------------------------------

def test_polygons_causes_match_masks_causes(standard_settings: SafetySettings) -> None:
    """Les causes des polygones sont un sous-ensemble des causes des masques actives."""
    layers = make_layers(has_obstacle=True, has_dune=True)
    site, _ = make_site(layers)

    masks = hazard_masks(site, standard_settings)
    polys = hazard_polygons(site, standard_settings)

    active_causes = {
        cause for cause, arr in masks.by_cause.items() if arr.any()
    }
    poly_causes = {f.properties["cause"] for f in polys.features}

    # Les causes des polygones doivent être dans les causes actives des masques
    for cause in poly_causes:
        assert cause in active_causes, (
            f"Cause de polygone {cause!r} absente des masques actifs {active_causes}"
        )


def test_polygons_present_for_active_causes(standard_settings: SafetySettings) -> None:
    """Chaque cause active a au moins un polygone (sur une grille de taille suffisante)."""
    # On utilise le site fictif qui a toutes les couches
    from marswalk_core.site_package import load_site
    site = load_site("fictif")

    masks = hazard_masks(site, standard_settings)
    polys = hazard_polygons(site, standard_settings)
    poly_causes = {f.properties["cause"] for f in polys.features}

    active_causes = {
        cause for cause, arr in masks.by_cause.items()
        if arr.sum() >= 25  # au moins 25 cases pour générer un polygone visible
    }

    for cause in active_causes:
        assert cause in poly_causes, (
            f"Cause {cause!r} active dans les masques mais absente des polygones"
        )


# ---------------------------------------------------------------------------
# Effet d'un changement de seuil sur les trois objets simultanément
# ---------------------------------------------------------------------------

def test_threshold_change_affects_masks_polygons_grid() -> None:
    """Modifier max_slope_deg change masques, polygones ET grille conjointement."""
    layers = make_layers(slope_val=18.0)
    site, _ = make_site(layers)

    settings_20 = SafetySettings(max_slope_deg=20.0, penalty_slope_deg=10.0)
    settings_15 = SafetySettings(max_slope_deg=15.0, penalty_slope_deg=8.0)

    # Masques
    masks_20 = hazard_masks(site, settings_20)
    masks_15 = hazard_masks(site, settings_15)
    assert not masks_20.forbidden.any()
    assert masks_15.forbidden.all()

    # Polygones
    polys_20 = hazard_polygons(site, settings_20)
    polys_15 = hazard_polygons(site, settings_15)
    # Avec seuil 15°, la zone entière est interdite → au moins un polygone forbidden
    forbidden_poly_15 = [f for f in polys_15.features if f.properties["kind"] == "forbidden"]
    assert len(forbidden_poly_15) > 0, "Aucun polygone forbidden avec seuil 15°"
    # Avec seuil 20°, la zone est pénalisée (pas interdite) → polygon kind=penalized
    forbidden_poly_20 = [f for f in polys_20.features if f.properties["kind"] == "forbidden"
                         and f.properties["cause"] == "slope_forbidden"]
    assert len(forbidden_poly_20) == 0, "Polygone slope_forbidden trouvé avec seuil 20° (pente=18°)"

    # Grille
    grid_20 = build_cost_grid(site, settings_20)
    grid_15 = build_cost_grid(site, settings_15)
    assert not np.any(np.isinf(grid_20.cost)), "Aucune cellule inf attendue avec seuil 20°"
    assert np.all(np.isinf(grid_15.cost)), "Toutes les cellules inf attendues avec seuil 15°"


def test_scarp_buffer_change_affects_all() -> None:
    """Modifier scarp_buffer_m change conjointement les trois objets."""
    layers = make_layers(has_scarp=True)
    site, _ = make_site(layers)

    s_small = SafetySettings(scarp_buffer_m=2.0, max_slope_deg=20.0)
    s_large = SafetySettings(scarp_buffer_m=16.0, max_slope_deg=20.0)

    masks_small = hazard_masks(site, s_small)
    masks_large = hazard_masks(site, s_large)

    inf_small = int(masks_small.by_cause["scarp"].sum())
    inf_large = int(masks_large.by_cause["scarp"].sum())
    assert inf_large > inf_small

    grid_small = build_cost_grid(site, s_small)
    grid_large = build_cost_grid(site, s_large)
    assert int(np.isinf(grid_large.cost).sum()) > int(np.isinf(grid_small.cost).sum())


# ---------------------------------------------------------------------------
# Préréglages standard vs prudent
# ---------------------------------------------------------------------------

def test_prudent_more_restrictive_than_standard(
    standard_settings: SafetySettings,
    prudent_settings: SafetySettings,
) -> None:
    """Le préréglage 'prudent' interdit plus de zones que 'standard'."""
    from marswalk_core.site_package import load_site
    site = load_site("fictif")

    masks_std = hazard_masks(site, standard_settings)
    masks_pru = hazard_masks(site, prudent_settings)

    # Le préréglage prudent a max_slope_deg=15° vs 20° → plus de zones interdites
    assert int(masks_pru.forbidden.sum()) > int(masks_std.forbidden.sum()), (
        "Le préréglage prudent doit interdire plus de zones que standard"
    )

    grid_std = build_cost_grid(site, standard_settings)
    grid_pru = build_cost_grid(site, prudent_settings)

    inf_std = int(np.isinf(grid_std.cost).sum())
    inf_pru = int(np.isinf(grid_pru.cost).sum())
    assert inf_pru > inf_std


# ---------------------------------------------------------------------------
# by_cause ↔ forbidden/penalized union
# ---------------------------------------------------------------------------

def test_forbidden_is_union_of_forbidden_causes(standard_settings: SafetySettings) -> None:
    """masks.forbidden == union de toutes les causes forbidden dans by_cause."""
    layers = make_layers(slope_val=10.0, has_obstacle=True, has_dune=True, has_scarp=True)
    layers["slope"][:20, :] = 25.0
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)

    forbidden_cause_keys = ["slope_forbidden", "obstacle", "dune", "scarp"]
    union = np.zeros(masks.forbidden.shape, dtype=bool)
    for k in forbidden_cause_keys:
        if k in masks.by_cause:
            union |= masks.by_cause[k]

    np.testing.assert_array_equal(masks.forbidden, union)
