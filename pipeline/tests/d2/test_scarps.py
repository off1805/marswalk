"""Tests de la couche dérivée : scarps."""

from __future__ import annotations

import numpy as np

from marswalk_pipeline.derived.scarps import compute_scarps

NODATA = -9999.0
RES = 1.0


class TestFlatNoScarps:
    def test_flat_no_scarps(self, flat_dem):
        """DEM plat → pente=0 → aucune falaise."""
        from marswalk_pipeline.derived.slope import compute_slope

        slope = compute_slope(flat_dem, RES, nodata=NODATA)
        result = compute_scarps(
            slope, threshold_deg=30.0, buffer_m=0.0, resolution_m=RES, nodata=NODATA
        )
        valid = result != NODATA
        assert valid.any()
        assert np.all(result[valid] == 0.0), "DEM plat ne devrait pas avoir de falaises"


class TestCliffDetected:
    def test_cliff_detected(self, dem_with_cliff):
        """Falaise > threshold → 1."""
        from marswalk_pipeline.derived.slope import compute_slope

        slope = compute_slope(dem_with_cliff, RES, nodata=NODATA)
        result = compute_scarps(
            slope, threshold_deg=30.0, buffer_m=0.0, resolution_m=RES, nodata=NODATA
        )
        # La falaise à la colonne 50 doit être détectée
        col_49 = result[:, 49]  # juste avant la falaise
        col_50 = result[:, 50]  # à la falaise
        valid_49 = col_49 != NODATA
        valid_50 = col_50 != NODATA
        # Au moins quelques pixels à la falaise doivent être marqués 1
        assert (valid_50.any() and float(col_50[valid_50].max()) == 1.0) or (
            valid_49.any() and float(col_49[valid_49].max()) == 1.0
        ), "Falaise non détectée"


class TestBufferApplied:
    def test_buffer_applied(self):
        """buffer > 0 → zone falaise plus large."""
        # DEM avec une falaise ponctuelle
        size = 50
        slope = np.zeros((size, size), dtype=np.float32)
        slope[25, 25] = 45.0  # pente très forte en un seul pixel

        result_no_buf = compute_scarps(
            slope, threshold_deg=30.0, buffer_m=0.0, resolution_m=RES, nodata=NODATA
        )
        result_buf = compute_scarps(
            slope, threshold_deg=30.0, buffer_m=5.0, resolution_m=RES, nodata=NODATA
        )

        n_no_buf = int(np.sum(result_no_buf == 1.0))
        n_buf = int(np.sum(result_buf == 1.0))
        assert n_buf > n_no_buf, f"Tampon devrait agrandir la zone : {n_buf} vs {n_no_buf}"


class TestNodataPropagation:
    def test_nodata_propagation(self):
        """Pixels nodata en entrée → nodata en sortie."""
        slope = np.full((50, 50), 10.0, dtype=np.float32)
        slope[10, 10] = NODATA
        result = compute_scarps(
            slope, threshold_deg=30.0, buffer_m=0.0, resolution_m=RES, nodata=NODATA
        )
        assert result[10, 10] == NODATA


class TestBinaryOutput:
    def test_binary_output(self, dem_with_cliff):
        """Seules les valeurs 0.0, 1.0 et nodata."""
        from marswalk_pipeline.derived.slope import compute_slope

        slope = compute_slope(dem_with_cliff, RES, nodata=NODATA)
        result = compute_scarps(
            slope, threshold_deg=30.0, buffer_m=5.0, resolution_m=RES, nodata=NODATA
        )
        unique_vals = set(np.unique(result).tolist())
        allowed = {0.0, 1.0, NODATA}
        assert unique_vals.issubset(allowed), f"Valeurs inattendues : {unique_vals - allowed}"
