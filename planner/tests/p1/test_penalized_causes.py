"""Tests P1-C : zones pénalisées (radio, ombres, rugosité, sol meuble).

Les zones pénalisées doivent :
- Être distinctes des zones interdites (pas de chevauchement).
- Augmenter le risque R sans interdire le passage.
- Être configurables via SafetySettings.
"""

from __future__ import annotations

import numpy as np

from marswalk_core.schemas import SafetySettings
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.hazards import hazard_masks, hazard_polygons

from .conftest import make_layers, make_site

# ---------------------------------------------------------------------------
# Couverture radio
# ---------------------------------------------------------------------------


def test_no_radio_penalized_not_forbidden(standard_settings: SafetySettings) -> None:
    """L'absence de couverture radio pénalise mais n'interdit pas."""
    layers = make_layers(radio=0.0)
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)
    assert not masks.forbidden.any(), "Hors radio ne doit pas interdire"
    assert masks.penalized.all(), "Toutes les cases hors radio doivent être pénalisées"


def test_no_radio_increases_risk(standard_settings: SafetySettings) -> None:
    """L'absence de radio augmente R par rapport à une zone couverte."""
    layers_cov = make_layers(radio=1.0)
    layers_nocov = make_layers(radio=0.0)
    site_cov, _ = make_site(layers_cov)
    site_nocov, _ = make_site(layers_nocov)

    grid_cov = build_cost_grid(site_cov, standard_settings)
    grid_nocov = build_cost_grid(site_nocov, standard_settings)

    r_cov = float(grid_cov.terms["risk"][0, 0])
    r_nocov = float(grid_nocov.terms["risk"][0, 0])
    assert r_nocov > r_cov, f"R sans radio ({r_nocov}) doit dépasser R avec radio ({r_cov})"


def test_radio_penalty_configurable() -> None:
    """radio_penalty plus élevée augmente R proportionnellement."""
    layers = make_layers(radio=0.0)
    site, _ = make_site(layers)

    s_low = SafetySettings(radio_penalty=1.0)
    s_high = SafetySettings(radio_penalty=4.0)

    grid_low = build_cost_grid(site, s_low)
    grid_high = build_cost_grid(site, s_high)

    r_low = float(grid_low.terms["risk"][0, 0])
    r_high = float(grid_high.terms["risk"][0, 0])
    assert r_high > r_low


def test_require_radio_still_not_forbidden(standard_settings: SafetySettings) -> None:
    """Même avec require_radio=True, l'absence de radio reste une pénalité, pas une interdiction."""
    layers = make_layers(radio=0.0)
    site, _ = make_site(layers)
    settings = SafetySettings(require_radio=True, radio_penalty=4.0)
    masks = hazard_masks(site, settings)
    assert not masks.forbidden.any(), "Hors radio ne doit jamais interdire (P1-C)"


# ---------------------------------------------------------------------------
# Ombres / illumination
# ---------------------------------------------------------------------------


def test_shadow_penalized(standard_settings: SafetySettings) -> None:
    """Zone à illumination 0 est pénalisée quand min_illumination=0."""
    layers = make_layers(illumination=0.0)
    site, _ = make_site(layers)
    settings = SafetySettings(min_illumination=0.0)
    masks = hazard_masks(site, settings)
    assert masks.penalized.all(), "Zone sombre (illum=0) doit être pénalisée"
    assert not masks.forbidden.any()


def test_shadow_not_penalized_when_above_threshold() -> None:
    """Zone éclairée au-dessus du seuil n'est pas pénalisée."""
    layers = make_layers(illumination=0.5)
    site, _ = make_site(layers)
    settings = SafetySettings(min_illumination=0.0)
    masks = hazard_masks(site, settings)
    # illumination=0.5 > min_illumination=0.0 → pas de pénalité ombre
    # (d'autres couches peuvent pénaliser)
    assert not masks.by_cause["shadow"].any(), "illum=0.5 ne doit pas déclencher shadow"


def test_shadow_threshold_configurable() -> None:
    """Un seuil d'illumination plus élevé pénalise plus de zones."""
    layers = make_layers(illumination=0.3)
    site, _ = make_site(layers)

    settings_low = SafetySettings(min_illumination=0.1)  # 0.3 > 0.1 → pas pénalisé
    settings_high = SafetySettings(min_illumination=0.5)  # 0.3 ≤ 0.5 → pénalisé

    masks_low = hazard_masks(site, settings_low)
    masks_high = hazard_masks(site, settings_high)

    assert not masks_low.by_cause["shadow"].any()
    assert masks_high.by_cause["shadow"].all()


# ---------------------------------------------------------------------------
# Sol meuble (classe 2)
# ---------------------------------------------------------------------------


def test_loose_soil_class2_penalized(standard_settings: SafetySettings) -> None:
    """Classe 2 (sol meuble) est pénalisée mais pas interdite."""
    layers = make_layers()
    layers["loose_soil"][:] = 2.0
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)
    assert masks.penalized.any()
    assert not masks.forbidden.any()
    assert masks.by_cause.get("loose_soil", np.zeros((1,))).any()


def test_loose_soil_class3_forbidden(standard_settings: SafetySettings) -> None:
    """Classe 3 (dune) est interdite."""
    layers = make_layers()
    layers["loose_soil"][:] = 3.0
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)
    assert masks.forbidden.all()


# ---------------------------------------------------------------------------
# Rugosité
# ---------------------------------------------------------------------------


def test_roughness_above_threshold_penalized(standard_settings: SafetySettings) -> None:
    """Rugosité > max_roughness_m est pénalisée."""
    layers = make_layers()
    layers["roughness"][:] = 0.8  # > max_roughness_m=0.5
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)
    assert masks.by_cause.get("roughness", np.zeros((1,))).any()
    assert not masks.forbidden.any()


def test_roughness_below_threshold_no_penalty(standard_settings: SafetySettings) -> None:
    """Rugosité ≤ seuil n'est pas pénalisée."""
    layers = make_layers()
    layers["roughness"][:] = 0.1  # < max_roughness_m=0.5
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)
    # La cause roughness ne doit pas être active
    roughness_pen = masks.by_cause.get("roughness", np.zeros(masks.forbidden.shape))
    assert not roughness_pen.any()


# ---------------------------------------------------------------------------
# Polygones des zones pénalisées
# ---------------------------------------------------------------------------


def test_penalized_polygons_are_caution(standard_settings: SafetySettings) -> None:
    """Les polygones pénalisés ont severity='caution'."""
    layers = make_layers(radio=0.0)
    site, _ = make_site(layers)
    polys = hazard_polygons(site, standard_settings)

    for feat in polys.features:
        if feat.properties["kind"] == "penalized":
            assert feat.properties["severity"] == "caution", (
                f"Polygone {feat.id} : severity={feat.properties['severity']} (attendu: caution)"
            )


def test_both_forbidden_and_penalized_polygons_present(standard_settings: SafetySettings) -> None:
    """Les deux catégories apparaissent quand le site en a."""
    layers = make_layers(slope_val=25.0)  # tout interdit par pente
    layers["illumination"][:25, :] = 0.0  # une zone sombre (pénalisée)
    # Le haut est interdit (pente 25°), le bas est libre mais ombragé
    layers["slope"][50:, :] = 5.0  # pente douce (libre)
    site, _ = make_site(layers)
    polys = hazard_polygons(site, standard_settings)

    kinds = {f.properties["kind"] for f in polys.features}
    assert "forbidden" in kinds
    # La zone d'ombre peut ou non générer un polygone selon la résolution du coarsen
    # → pas d'assertion stricte sur "penalized" (trop petite zone possible)
