"""Tests de la couche dérivée : slope."""

from __future__ import annotations

import numpy as np

from marswalk_pipeline.derived.slope import compute_slope

NODATA = -9999.0
RES = 1.0  # m/px


class TestFlatDem:
    def test_flat_dem_gives_zero_slope(self, flat_dem: np.ndarray) -> None:
        slope = compute_slope(flat_dem, RES, nodata=NODATA)
        valid = slope != NODATA
        assert valid.any(), "Aucun pixel valide"
        assert np.allclose(slope[valid], 0.0, atol=1e-4), (
            f"DEM plat devrait donner pente=0, max={slope[valid].max():.4f}"
        )


class TestTiltedDem:
    def test_tilted_dem_slope_accuracy(self, tilted_dem: np.ndarray) -> None:
        """Plan incliné 15° → pente retrouvée à 0.1° près (pixels intérieurs)."""
        slope = compute_slope(tilted_dem, RES, nodata=NODATA)
        # Exclure les bords (1 pixel) où le gradient est moins précis
        interior = slope[1:-1, 1:-1]
        valid = interior != NODATA
        assert valid.any()
        mean_slope = float(np.mean(interior[valid]))
        assert abs(mean_slope - 15.0) < 0.1, f"Pente attendue 15.0°, obtenu {mean_slope:.4f}°"


class TestNodataPropagation:
    def test_nodata_propagation(self, flat_dem: np.ndarray) -> None:
        """Les pixels nodata en entrée → nodata en sortie."""
        dem = flat_dem.copy()
        dem[10, 10] = NODATA
        dem[20:25, 20:25] = NODATA

        slope = compute_slope(dem, RES, nodata=NODATA)
        assert slope[10, 10] == NODATA
        assert np.all(slope[20:25, 20:25] == NODATA)


class TestSlopeRange:
    def test_slope_range(self, dem_with_cliff: np.ndarray) -> None:
        """Toutes les valeurs valides ∈ [0, 90]."""
        slope = compute_slope(dem_with_cliff, RES, nodata=NODATA)
        valid = slope != NODATA
        assert valid.any()
        assert float(slope[valid].min()) >= 0.0
        assert float(slope[valid].max()) <= 90.0


class TestSlopeDimsAndCrs:
    def test_slope_crs_and_dims(self, flat_dem: np.ndarray) -> None:
        """Le raster de sortie a les bonnes dimensions."""
        slope = compute_slope(flat_dem, RES, nodata=NODATA)
        assert slope.shape == flat_dem.shape
        assert slope.dtype == np.float32
