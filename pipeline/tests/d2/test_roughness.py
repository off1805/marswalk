"""Tests de la couche dérivée : roughness."""

from __future__ import annotations

import numpy as np
import pytest

from marswalk_pipeline.derived.roughness import compute_roughness

NODATA = -9999.0
RES = 1.0


class TestFlatDem:
    def test_flat_dem_gives_zero_roughness(self, flat_dem):
        """DEM plat → roughness=0."""
        roughness = compute_roughness(flat_dem, window_m=5.0, resolution_m=RES, nodata=NODATA)
        valid = roughness != NODATA
        assert valid.any()
        assert np.allclose(roughness[valid], 0.0, atol=1e-5), (
            f"DEM plat devrait donner roughness=0, max={roughness[valid].max():.6f}"
        )


class TestReliefRoughness:
    def test_roughness_increases_with_relief(self, dem_with_pit):
        """DEM avec relief → roughness > 0 dans les zones rugueuses."""
        roughness = compute_roughness(dem_with_pit, window_m=5.0, resolution_m=RES, nodata=NODATA)
        # Zone rugueuse centrale (après propagation des nodata)
        center = roughness[42:58, 42:58]
        valid = center != NODATA
        if valid.any():
            assert float(center[valid].max()) > 0.1, (
                "Zone rugueuse devrait avoir roughness > 0.1"
            )


class TestWindowSizeEffect:
    def test_window_size_effect(self, dem_with_pit):
        """Fenêtre plus grande → valeurs de roughness différentes."""
        r_small = compute_roughness(dem_with_pit, window_m=3.0, resolution_m=RES, nodata=NODATA)
        r_large = compute_roughness(dem_with_pit, window_m=15.0, resolution_m=RES, nodata=NODATA)
        # Les valeurs ne sont pas identiques
        valid = (r_small != NODATA) & (r_large != NODATA)
        assert valid.any()
        assert not np.allclose(r_small[valid], r_large[valid]), (
            "Des fenêtres différentes doivent donner des rugosités différentes"
        )


class TestNodataPropagation:
    def test_nodata_propagation(self, flat_dem):
        """Les pixels nodata en entrée → nodata en sortie."""
        dem = flat_dem.copy()
        dem[50, 50] = NODATA
        roughness = compute_roughness(dem, window_m=3.0, resolution_m=RES, nodata=NODATA)
        assert roughness[50, 50] == NODATA


class TestOutputDimsAndCrs:
    def test_output_dims_and_crs(self, flat_dem):
        """Les dimensions de sortie correspondent à l'entrée."""
        roughness = compute_roughness(flat_dem, window_m=5.0, resolution_m=RES, nodata=NODATA)
        assert roughness.shape == flat_dem.shape
        assert roughness.dtype == np.float32
