"""Tests P1-B : obstacles, dunes, tampon de falaise.

Hypothèses :
- obstacles == 1  → interdit (rule : bloc détecté)
- loose_soil >= avoid_loose_soil_class (3) → interdit (dune active)
- scarps == 1 → interdit après dilation d'un tampon configurable
- Le tampon s'exprime en mètres ; à résolution 2 m et scarp_buffer_m=10 m,
  le rayon vaut ceil((10 + 0 + 2) / 2) = 6 cases.
"""

from __future__ import annotations

import numpy as np

from marswalk_core.schemas import SafetySettings
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.hazards import hazard_masks, hazard_polygons

from .conftest import GRID_SIZE, make_layers, make_site

# ---------------------------------------------------------------------------
# Obstacles
# ---------------------------------------------------------------------------


def test_obstacle_cells_forbidden(standard_settings: SafetySettings) -> None:
    """Les cases obstacles sont interdites."""
    layers = make_layers(has_obstacle=True)
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)

    half = GRID_SIZE // 2
    # Zone obstacle
    obs_zone = masks.forbidden[:half, :half]
    free_zone = masks.forbidden[half:, half:]
    assert obs_zone.all(), "Toute la zone obstacle doit être interdite"
    assert not free_zone.any(), "La zone libre ne doit pas être interdite"


def test_obstacle_forbidden_in_by_cause(standard_settings: SafetySettings) -> None:
    """La cause 'obstacle' est présente dans by_cause."""
    layers = make_layers(has_obstacle=True)
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)
    assert "obstacle" in masks.by_cause
    assert masks.by_cause["obstacle"].any()


def test_obstacle_inf_cost(standard_settings: SafetySettings) -> None:
    """Les cellules obstacle ont coût +inf."""
    layers = make_layers(has_obstacle=True)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)
    half = GRID_SIZE // 2
    assert np.all(np.isinf(grid.cost[:half, :half]))


def test_obstacle_polygon_present(standard_settings: SafetySettings) -> None:
    """hazard_polygons produit un feature de cause 'obstacle'."""
    layers = make_layers(has_obstacle=True)
    site, _ = make_site(layers)
    polys = hazard_polygons(site, standard_settings)
    causes = {f.properties["cause"] for f in polys.features}
    assert "obstacle" in causes


# ---------------------------------------------------------------------------
# Dunes actives
# ---------------------------------------------------------------------------


def test_dune_cells_forbidden(standard_settings: SafetySettings) -> None:
    """Les cases loose_soil==3 (dunes) sont interdites."""
    layers = make_layers(has_dune=True)
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)

    half = GRID_SIZE // 2
    dune_zone = masks.forbidden[:half, :half]
    free_zone = masks.forbidden[half:, half:]
    assert dune_zone.all(), "La zone dunes doit être interdite"
    assert not free_zone.any()


def test_dune_forbidden_cause(standard_settings: SafetySettings) -> None:
    """La cause 'dune' est enregistrée."""
    layers = make_layers(has_dune=True)
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)
    assert "dune" in masks.by_cause
    assert masks.by_cause["dune"].any()


def test_dune_loose_soil_class2_penalized(standard_settings: SafetySettings) -> None:
    """La classe 2 (sol meuble) est pénalisée mais pas interdite."""
    layers = make_layers()
    layers["loose_soil"][:] = 2.0  # classe meuble
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)
    assert not masks.forbidden.any(), "Sol classe 2 ne doit pas être interdit"
    assert masks.penalized.any(), "Sol classe 2 doit être pénalisé"


def test_dune_avoid_class_configurable() -> None:
    """Changer avoid_loose_soil_class change les zones interdites."""
    layers = make_layers()
    layers["loose_soil"][:] = 2.0  # classe 2 partout
    site, _ = make_site(layers)

    # Avec seuil 3 : classe 2 est pénalisée, pas interdite
    settings_3 = SafetySettings(max_slope_deg=20.0, avoid_loose_soil_class=3)
    masks_3 = hazard_masks(site, settings_3)
    assert not masks_3.forbidden.any()

    # Avec seuil 2 : classe 2 est interdite
    settings_2 = SafetySettings(max_slope_deg=20.0, avoid_loose_soil_class=2)
    masks_2 = hazard_masks(site, settings_2)
    assert masks_2.forbidden.all()


# ---------------------------------------------------------------------------
# Tampon de falaise (scarp buffer)
# ---------------------------------------------------------------------------


def test_scarp_buffer_extends_forbidden_zone(standard_settings: SafetySettings) -> None:
    """La dilation du tampon étend la zone interdite au-delà de la ligne de falaise."""
    layers = make_layers(has_scarp=True)
    site, _ = make_site(layers)
    masks = hazard_masks(site, standard_settings)

    half = GRID_SIZE // 2
    scarp_row = half  # ligne de falaise

    # La ligne de falaise elle-même est interdite
    assert masks.by_cause["scarp"][scarp_row, :].all(), "La ligne de falaise doit être interdite"

    # Les lignes voisines (tampon de 6 cases à résolution 2 m et scarp_buffer_m=10 m)
    # doivent aussi être interdites
    assert masks.forbidden[scarp_row - 1, :].all(), "La ligne adjacente doit être dans le tampon"
    assert masks.forbidden[scarp_row + 1, :].all(), "La ligne adjacente doit être dans le tampon"


def test_scarp_buffer_configurable() -> None:
    """Un tampon plus petit laisse des cellules libres plus près de la falaise."""
    layers = make_layers(has_scarp=True)
    site, _ = make_site(layers)

    # Tampon de 2 m (1 case) : seule la ligne elle-même + 1 voisin
    settings_small = SafetySettings(max_slope_deg=20.0, scarp_buffer_m=2.0)
    # Tampon de 20 m (10 cases)
    settings_large = SafetySettings(max_slope_deg=20.0, scarp_buffer_m=20.0)

    masks_small = hazard_masks(site, settings_small)
    masks_large = hazard_masks(site, settings_large)

    # Le tampon large a plus de cellules interdites par la cause scarp
    scarp_small = int(masks_small.by_cause["scarp"].sum())
    scarp_large = int(masks_large.by_cause["scarp"].sum())
    assert scarp_large > scarp_small, (
        f"Tampon 20 m ({scarp_large}) doit couvrir plus que tampon 2 m ({scarp_small})"
    )


def test_scarp_buffer_causes_no_passage(standard_settings: SafetySettings) -> None:
    """Toutes les cellules dans le tampon sont inaccessibles à P2 (coût +inf)."""
    layers = make_layers(has_scarp=True)
    site, _ = make_site(layers)
    grid = build_cost_grid(site, standard_settings)

    scarp_forbidden = grid.terms["cause_scarp"].astype(bool)
    # Toutes les cases du tampon doivent avoir coût inf
    assert np.all(np.isinf(grid.cost[scarp_forbidden])), (
        "Certaines cases du tampon de falaise ont un coût fini "
        "— elles ne doivent pas être traversables."
    )


# ---------------------------------------------------------------------------
# Polygones GeoJSON
# ---------------------------------------------------------------------------


def test_polygons_have_severity_field(standard_settings: SafetySettings) -> None:
    """Chaque polygone a les champs requis (severity, cause, kind, color)."""
    layers = make_layers(has_obstacle=True, has_dune=True)
    site, _ = make_site(layers)
    polys = hazard_polygons(site, standard_settings)

    for feat in polys.features:
        assert "severity" in feat.properties
        assert "cause" in feat.properties
        assert "kind" in feat.properties
        assert "color" in feat.properties
        assert feat.properties["severity"] in ("danger", "caution")


def test_polygons_forbidden_are_danger(standard_settings: SafetySettings) -> None:
    """Les polygones interdits ont severity='danger'."""
    layers = make_layers(has_obstacle=True)
    site, _ = make_site(layers)
    polys = hazard_polygons(site, standard_settings)

    for feat in polys.features:
        if feat.properties["kind"] == "forbidden":
            assert feat.properties["severity"] == "danger"


def test_polygons_fewer_than_one_per_cell(standard_settings: SafetySettings) -> None:
    """Le nombre de polygones est bien inférieur au nombre de cellules (regroupement)."""
    layers = make_layers(slope_val=15.0)
    site, _ = make_site(layers)
    polys = hazard_polygons(site, standard_settings)
    total_cells = GRID_SIZE * GRID_SIZE
    assert len(polys.features) < total_cells, (
        f"Trop de polygones ({len(polys.features)}) pour {total_cells} cellules"
    )


def test_polygons_coordinates_are_finite(standard_settings: SafetySettings) -> None:
    """Toutes les coordonnées des polygones sont finies (pas de NaN)."""
    layers = make_layers(has_obstacle=True, has_dune=True, has_scarp=True)
    site, _ = make_site(layers)
    polys = hazard_polygons(site, standard_settings)
    for feat in polys.features:
        for ring in feat.geometry.coordinates:
            for pt in ring:
                assert np.isfinite(pt.lon) and np.isfinite(pt.lat), (
                    f"Coordonnée non finie dans le polygone {feat.id}"
                )
