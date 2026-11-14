import math

import numpy as np
import pytest

from marswalk_core.config import (
    load_display_presets,
    load_safety_presets,
    load_safety_settings,
    load_suit,
)
from marswalk_core.geodesy import distance_m, to_analysis, to_lonlat
from marswalk_core.schemas import KNOWN_LAYER_IDS, LonLat
from marswalk_core.site_package import LayerUnavailableError, load_site


@pytest.fixture(scope="module")
def site():  # type: ignore[no-untyped-def]
    return load_site("fictif")


def test_manifest_has_every_catalogue_layer(site) -> None:  # type: ignore[no-untyped-def]
    ids = {layer.id for layer in site.manifest.layers}
    assert set(KNOWN_LAYER_IDS) <= ids
    for layer in site.manifest.layers:
        assert layer.source.instrument == "SYNTHETIC"


def test_read_layer_is_on_analysis_grid(site) -> None:  # type: ignore[no-untyped-def]
    slope = site.read_layer("slope")
    assert slope.shape == site.shape == (1000, 1000)
    assert slope.dtype == np.float32
    assert float(slope.x[1] - slope.x[0]) == pytest.approx(2.0)
    window = site.read_layer("dem", window=(10, 20, 30, 40))
    assert window.shape == (40, 30)


def test_sample_inside_and_outside(site) -> None:  # type: ignore[no-untyped-def]
    hab = site.manifest.habitat
    elev = site.sample("dem", hab.lon, hab.lat)
    assert elev is not None and -2700 < elev < -2500
    west, south, _, _ = site.manifest.bbox
    assert site.sample("dem", west - 0.01, south - 0.01) is None
    assert site.sample("couche_inconnue", hab.lon, hab.lat) is None
    with pytest.raises(LayerUnavailableError):
        site.read_layer("couche_inconnue")


def test_fictitious_features_are_present(site) -> None:  # type: ignore[no-untyped-def]
    assert float(site.read_layer("scarps").max()) == 1.0
    assert float(site.read_layer("loose_soil").max()) == 3.0
    assert set(np.unique(site.read_layer("crism_minerals").values)) == {0.0, 1.0, 2.0}
    radio = site.read_layer("radio_coverage").values
    assert 0.0 < radio.mean() < 1.0


def test_analysis_round_trip(site) -> None:  # type: ignore[no-untyped-def]
    hab = site.manifest.habitat
    x, y = to_analysis(site, hab.lon, hab.lat)
    lon, lat = to_lonlat(site, x, y)
    assert lon == pytest.approx(hab.lon, abs=1e-9)
    assert lat == pytest.approx(hab.lat, abs=1e-9)


def test_one_degree_at_equator() -> None:
    d = distance_m(LonLat(0, 0), LonLat(1, 0))
    assert d == pytest.approx(2 * math.pi * 3_396_190 / 360, rel=1e-9)
    assert 59_000 < d < 59_500


def test_configs_load() -> None:
    assert load_safety_settings().max_slope_deg == 20.0
    assert set(load_safety_presets()) >= {"standard", "prudent"}
    assert load_suit().oxygen_capacity_kg > 0
    assert {p.id for p in load_display_presets()} == {"safety", "science", "navigation"}
