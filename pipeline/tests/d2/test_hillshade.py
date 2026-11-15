"""Tests de la couche dérivée : hillshade."""

from __future__ import annotations

import numpy as np

from marswalk_pipeline.derived.hillshade import compute_hillshade

NODATA = -9999.0
RES = 1.0


class TestFlatDem:
    def test_flat_dem_gives_uniform_hillshade(self, flat_dem):
        """DEM plat → hillshade uniforme (même valeur partout)."""
        hs = compute_hillshade(
            flat_dem, RES, sun_azimuth_deg=315.0, sun_altitude_deg=45.0, nodata=NODATA
        )
        valid = hs != NODATA
        assert valid.any()
        vals = hs[valid]
        # Tous les pixels doivent avoir la même valeur sur un plan horizontal
        assert float(vals.max() - vals.min()) < 1.0, (
            f"Hillshade non uniforme sur DEM plat : [{vals.min():.1f}, {vals.max():.1f}]"
        )


class TestRange:
    def test_range_0_255(self, dem_with_cliff):
        """Toutes les valeurs ∈ [0, 255]."""
        hs = compute_hillshade(
            dem_with_cliff, RES, sun_azimuth_deg=315.0, sun_altitude_deg=30.0, nodata=NODATA
        )
        valid = hs != NODATA
        assert valid.any()
        assert float(hs[valid].min()) >= 0.0
        assert float(hs[valid].max()) <= 255.0


class TestDirectionalSensitivity:
    def test_south_facing_slope_darker_eastward_sun(self):
        """Pente exposée est plus lumineuse avec Soleil à l'est.

        Convention : une pente "exposée est" descend vers l'est (normal pointant est).
        Avec le Soleil à l'est (azimut=90°), la pente exposée est doit être plus lumineuse
        que la pente exposée ouest.

        Note : une pente qui MONTE vers l'est a sa normale pointant OUEST (pente exposée ouest).
        """
        size = 50
        cols = np.arange(size, dtype=np.float32)

        # Pente exposée EST : DESCEND vers l'est (monte vers l'ouest)
        # dem_east_facing[r,c] = -2500 + (size-1-c) * slope
        dem_east_facing = np.broadcast_to(
            -2500.0 + (size - 1 - cols) * 0.577, (size, size)
        ).copy().astype(np.float32)

        # Pente exposée OUEST : DESCEND vers l'ouest (monte vers l'est)
        dem_west_facing = np.broadcast_to(
            -2500.0 + cols * 0.577, (size, size)
        ).copy().astype(np.float32)

        hs_east = compute_hillshade(
            dem_east_facing, RES, sun_azimuth_deg=90.0, sun_altitude_deg=30.0, nodata=NODATA
        )
        hs_west = compute_hillshade(
            dem_west_facing, RES, sun_azimuth_deg=90.0, sun_altitude_deg=30.0, nodata=NODATA
        )

        valid_e = hs_east != NODATA
        valid_w = hs_west != NODATA
        mean_e = float(hs_east[valid_e].mean())
        mean_w = float(hs_west[valid_w].mean())
        assert mean_e > mean_w, (
            "Pente exposée est devrait être plus lumineuse avec Soleil à l'est : "
            f"{mean_e:.1f} vs {mean_w:.1f}"
        )


class TestNodataPropagation:
    def test_nodata_propagation(self, flat_dem):
        """Les pixels nodata en entrée → nodata en sortie."""
        dem = flat_dem.copy()
        dem[30, 30] = NODATA
        hs = compute_hillshade(
            dem, RES, sun_azimuth_deg=315.0, sun_altitude_deg=45.0, nodata=NODATA
        )
        assert hs[30, 30] == NODATA
