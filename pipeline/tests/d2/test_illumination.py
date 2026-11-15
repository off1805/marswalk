"""Tests de la couche dérivée : illumination."""

from __future__ import annotations

import numpy as np

from marswalk_pipeline.derived.illumination import compute_illumination

NODATA = -9999.0
RES = 1.0


class TestFlatAllLit:
    def test_flat_all_lit(self):
        """DEM plat → tout éclairé (aucune ombre)."""
        size = 100
        dem = np.full((size, size), -2500.0, dtype=np.float32)
        result = compute_illumination(
            dem, RES, sun_azimuth_deg=90.0, sun_altitude_deg=20.0, nodata=NODATA
        )
        valid = result != NODATA
        assert valid.any()
        assert np.all(result[valid] == 1.0), (
            f"DEM plat devrait être tout éclairé, {np.sum(result[valid] == 0.0)} pixels en ombre"
        )


class TestEastFacingSlopeLit:
    def test_east_facing_slope_lit_by_east_sun(self):
        """Pente exposée est → éclairée avec Soleil à l'est.

        Note : une pente exposée EST descend vers l'est (monte vers l'ouest).
        Le DEM monte donc vers l'ouest (colonnes décroissantes).
        """
        size = 100
        # DEM montant vers l'OUEST (exposé EST) → descend vers l'est
        cols = np.arange(size, dtype=np.float32)
        dem = (
            np.broadcast_to(
                -2500.0 + (size - 1 - cols) * 0.364,
                (size, size),  # tan(20°)
            )
            .copy()
            .astype(np.float32)
        )

        # Soleil à l'est (azimut=90°, altitude=20°)
        result = compute_illumination(
            dem, RES, sun_azimuth_deg=90.0, sun_altitude_deg=20.0, nodata=NODATA
        )
        valid = result != NODATA
        assert valid.any()
        # La majorité des pixels doit être éclairée
        n_lit = int(np.sum(result[valid] == 1.0))
        n_total = int(np.sum(valid))
        frac_lit = n_lit / n_total
        assert frac_lit > 0.5, (
            f"Pente exposée est devrait être majoritairement éclairée : {frac_lit:.2f}"
        )


class TestDeepValleyShadowed:
    def test_deep_valley_shadowed(self):
        """Vallée profonde derrière une colline → en ombre."""
        size = 100
        dem = np.full((size, size), -2500.0, dtype=np.float32)
        # Crête haute à l'est (côté soleil)
        dem[:, 60:65] = -2400.0  # +100m de relief
        # Vallée derrière la crête (à l'ouest, côté ombre)
        # Avec Soleil à l'est (az=90°), l'ombre porte vers l'ouest

        result = compute_illumination(
            dem, RES, sun_azimuth_deg=90.0, sun_altitude_deg=10.0, nodata=NODATA
        )
        valid = result != NODATA
        assert valid.any()

        # Les pixels à l'ouest de la crête devraient être en ombre
        # La crête est à x=60-65, l'ombre porte vers l'ouest (x < 60)
        shadow_zone = result[:, 10:50]
        valid_s = shadow_zone != NODATA
        if valid_s.any():
            n_shadow = int(np.sum(shadow_zone[valid_s] == 0.0))
            assert n_shadow > 0, "Vallée derrière la crête devrait avoir des pixels en ombre"


class TestBinaryOutput:
    def test_binary_output(self):
        """Seules les valeurs 0.0, 1.0 et nodata."""
        size = 50
        dem = np.full((size, size), -2500.0, dtype=np.float32)
        dem[10, 10] = NODATA
        dem[:, 25:30] = -2420.0  # crête
        result = compute_illumination(
            dem, RES, sun_azimuth_deg=90.0, sun_altitude_deg=20.0, nodata=NODATA
        )
        allowed = {0.0, 1.0, NODATA}
        unique_vals = set(np.unique(result).tolist())
        assert unique_vals.issubset(allowed), f"Valeurs inattendues : {unique_vals - allowed}"
