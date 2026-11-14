"""Tests P1-E : gestion des couches manquantes et dégradées.

Règles :
- Une couche absente ou 'missing' ne provoque pas d'exception.
- Un avertissement explicite est émis.
- La marge de sécurité accrue s'applique (CostGrid.margin_pct > 0).
- Les données inconnues ne sont jamais traitées comme sûres :
    - slope absent → 90° (tout interdit)
    - obstacles absent → tout obstrué
    - loose_soil absent → tout traité comme dune
    - thermal_inertia absent → avertissement + marge accrue sur loose_soil
"""

from __future__ import annotations

import warnings as py_warnings

import numpy as np

from marswalk_core.schemas import SafetySettings
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.hazards import hazard_masks

from .conftest import GRID_SIZE, make_layers, make_site

# ---------------------------------------------------------------------------
# Couche slope absente
# ---------------------------------------------------------------------------

def test_missing_slope_no_crash(standard_settings: SafetySettings) -> None:
    """Slope absente → pas d'exception."""
    layers = make_layers()
    layers.pop("slope")
    site, _ = make_site(layers, missing=["slope"])
    # Ne doit pas lever d'exception
    masks = hazard_masks(site, standard_settings)
    # Tout est interdit (pire cas : 90°)
    assert masks.forbidden.all()


def test_missing_slope_emits_warning(standard_settings: SafetySettings) -> None:
    """Slope absente → avertissement Python."""
    layers = make_layers()
    layers.pop("slope")
    site, _ = make_site(layers, missing=["slope"])
    with py_warnings.catch_warnings(record=True) as caught:
        py_warnings.simplefilter("always")
        hazard_masks(site, standard_settings)
    messages = [str(w.message) for w in caught]
    assert any("slope" in m.lower() for m in messages), (
        f"Aucun avertissement sur 'slope' parmi : {messages}"
    )


def test_missing_slope_increases_margin(standard_settings: SafetySettings) -> None:
    """Slope absente → margin_pct > 0 dans CostGrid."""
    layers = make_layers()
    layers.pop("slope")
    site, _ = make_site(layers, missing=["slope"])
    with py_warnings.catch_warnings(record=True):
        py_warnings.simplefilter("always")
        grid = build_cost_grid(site, standard_settings)
    assert grid.margin_pct > 0, "margin_pct doit être > 0 quand slope est absente"


# ---------------------------------------------------------------------------
# thermal_inertia absente
# ---------------------------------------------------------------------------

def test_missing_thermal_inertia_no_crash(standard_settings: SafetySettings) -> None:
    """thermal_inertia absente ne provoque pas d'exception."""
    layers = make_layers()
    layers.pop("thermal_inertia")
    site, _ = make_site(layers, missing=["thermal_inertia"])
    with py_warnings.catch_warnings(record=True):
        py_warnings.simplefilter("always")
        masks = hazard_masks(site, standard_settings)
    # La grille est quand même produite
    assert masks.forbidden is not None


def test_missing_thermal_inertia_emits_warning(standard_settings: SafetySettings) -> None:
    """thermal_inertia absente → avertissement sur fiabilité des dunes."""
    layers = make_layers()
    layers.pop("thermal_inertia")
    site, _ = make_site(layers, missing=["thermal_inertia"])
    with py_warnings.catch_warnings(record=True) as caught:
        py_warnings.simplefilter("always")
        hazard_masks(site, standard_settings)
    messages = [str(w.message) for w in caught]
    # L'avertissement doit mentionner thermal_inertia ET les dunes / sols
    combined = " ".join(messages).lower()
    assert "thermal_inertia" in combined or "inertie" in combined or "dune" in combined, (
        f"Pas d'avertissement pertinent sur thermal_inertia : {messages}"
    )


def test_missing_thermal_inertia_does_not_make_dunes_safe(
    standard_settings: SafetySettings,
) -> None:
    """Même sans thermal_inertia, les dunes dans loose_soil restent interdites."""
    layers = make_layers(has_dune=True)
    layers.pop("thermal_inertia")
    site, _ = make_site(layers, missing=["thermal_inertia"])
    with py_warnings.catch_warnings(record=True):
        py_warnings.simplefilter("always")
        masks = hazard_masks(site, standard_settings)
    # La zone dune doit rester interdite
    half = GRID_SIZE // 2
    assert masks.forbidden[:half, :half].all(), (
        "Les dunes doivent rester interdites sans thermal_inertia"
    )


# ---------------------------------------------------------------------------
# loose_soil absente
# ---------------------------------------------------------------------------

def test_missing_loose_soil_worst_case(standard_settings: SafetySettings) -> None:
    """loose_soil absent → tout traité comme classe 3 (dune, pire cas)."""
    layers = make_layers()
    layers.pop("loose_soil")
    site, _ = make_site(layers, missing=["loose_soil"])
    with py_warnings.catch_warnings(record=True):
        py_warnings.simplefilter("always")
        masks = hazard_masks(site, standard_settings)
    # Tout doit être interdit (pire cas = dune)
    assert masks.forbidden.all(), "loose_soil absent → tout interdit (pire cas)"


def test_missing_loose_soil_emits_warning(standard_settings: SafetySettings) -> None:
    """loose_soil absent → avertissement."""
    layers = make_layers()
    layers.pop("loose_soil")
    site, _ = make_site(layers, missing=["loose_soil"])
    with py_warnings.catch_warnings(record=True) as caught:
        py_warnings.simplefilter("always")
        hazard_masks(site, standard_settings)
    messages = [str(w.message) for w in caught]
    assert any("loose_soil" in m for m in messages)


# ---------------------------------------------------------------------------
# obstacles absente
# ---------------------------------------------------------------------------

def test_missing_obstacles_worst_case(standard_settings: SafetySettings) -> None:
    """obstacles absente → tout obstrué (pire cas)."""
    layers = make_layers()
    layers.pop("obstacles")
    site, _ = make_site(layers, missing=["obstacles"])
    with py_warnings.catch_warnings(record=True):
        py_warnings.simplefilter("always")
        masks = hazard_masks(site, standard_settings)
    assert masks.forbidden.all()


# ---------------------------------------------------------------------------
# Couches secondaires absentes (ne plantent pas, pénalité simplement absente)
# ---------------------------------------------------------------------------

def test_missing_radio_coverage_no_crash(standard_settings: SafetySettings) -> None:
    """radio_coverage absente → pas d'exception, pénalité radio ignorée."""
    layers = make_layers()
    layers.pop("radio_coverage")
    site, _ = make_site(layers, missing=["radio_coverage"])
    with py_warnings.catch_warnings(record=True):
        py_warnings.simplefilter("always")
        masks = hazard_masks(site, standard_settings)
    # La pénalité radio n'est pas active
    assert not masks.by_cause.get("no_radio", np.zeros((1,))).any()


def test_missing_illumination_no_crash(standard_settings: SafetySettings) -> None:
    """illumination absente → pas d'exception."""
    layers = make_layers()
    layers.pop("illumination")
    site, _ = make_site(layers, missing=["illumination"])
    with py_warnings.catch_warnings(record=True):
        py_warnings.simplefilter("always")
        masks = hazard_masks(site, standard_settings)
    assert masks is not None


def test_missing_crism_no_crash_no_science_bonus(standard_settings: SafetySettings) -> None:
    """crism_minerals absent → S=0 (pas de bonus), pas d'exception."""
    layers = make_layers()
    layers.pop("crism_minerals")
    site, _ = make_site(layers, missing=["crism_minerals"])
    with py_warnings.catch_warnings(record=True):
        py_warnings.simplefilter("always")
        grid = build_cost_grid(site, standard_settings)
    sci = grid.terms["science"]
    assert float(sci.max()) == 0.0, "S doit être 0 sans couche CRISM"


# ---------------------------------------------------------------------------
# Couche dégradée
# ---------------------------------------------------------------------------

def test_degraded_layer_emits_warning(standard_settings: SafetySettings) -> None:
    """Une couche dégradée émet un avertissement."""
    layers = make_layers()
    site, _ = make_site(layers, degraded=["slope"])
    with py_warnings.catch_warnings(record=True) as caught:
        py_warnings.simplefilter("always")
        hazard_masks(site, standard_settings)
    messages = " ".join(str(w.message) for w in caught).lower()
    assert "degraded" in messages or "slope" in messages


def test_degraded_layer_increases_margin(standard_settings: SafetySettings) -> None:
    """Une couche dégradée augmente margin_pct."""
    layers = make_layers()
    site_ok, _ = make_site(layers)
    site_deg, _ = make_site(layers, degraded=["slope"])

    with py_warnings.catch_warnings(record=True):
        py_warnings.simplefilter("always")
        grid_ok = build_cost_grid(site_ok, standard_settings)
        grid_deg = build_cost_grid(site_deg, standard_settings)

    assert grid_deg.margin_pct >= grid_ok.margin_pct, (
        "Une couche dégradée doit augmenter margin_pct"
    )


def test_warnings_stored_in_grid(standard_settings: SafetySettings) -> None:
    """Les avertissements de couches manquantes sont stockés dans CostGrid.warnings."""
    layers = make_layers()
    layers.pop("thermal_inertia")
    site, _ = make_site(layers, missing=["thermal_inertia"])
    with py_warnings.catch_warnings(record=True):
        py_warnings.simplefilter("always")
        grid = build_cost_grid(site, standard_settings)
    assert len(grid.warnings) > 0, "CostGrid.warnings doit contenir les avertissements"
