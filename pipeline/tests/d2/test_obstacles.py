"""Tests de la couche dérivée : obstacles."""

from __future__ import annotations

import numpy as np
import pytest

from marswalk_pipeline.derived.obstacles import compute_obstacles

NODATA = -9999.0
RES = 1.0


def _make_roughness(size=50, center_val=0.0):
    """Crée un tableau de roughness uniforme."""
    return np.full((size, size), center_val, dtype=np.float32)


class TestSmoothTerrain:
    def test_smooth_terrain_no_obstacles(self):
        """roughness < threshold → 0 partout."""
        roughness = _make_roughness(50, center_val=0.1)
        result = compute_obstacles(roughness, threshold_m=0.4, buffer_m=0.0, resolution_m=RES, nodata=NODATA)
        valid = result != NODATA
        assert valid.any()
        assert np.all(result[valid] == 0.0), "Terrain lisse ne devrait pas avoir d'obstacles"


class TestRoughZoneFlagged:
    def test_rough_zone_flagged(self):
        """Zone rugueuse → 1 avec tampon."""
        roughness = _make_roughness(50, center_val=0.0)
        roughness[20:30, 20:30] = 0.8  # zone rugueuse
        result = compute_obstacles(roughness, threshold_m=0.4, buffer_m=0.0, resolution_m=RES, nodata=NODATA)
        # La zone rugueuse doit être marquée 1
        assert float(result[25, 25]) == 1.0
        # Les zones lisses doivent être 0
        assert float(result[5, 5]) == 0.0


class TestBufferExpands:
    def test_buffer_expands_obstacle_zone(self):
        """buffer > 0 → zone obstacle plus large."""
        roughness = _make_roughness(50, center_val=0.0)
        roughness[25, 25] = 0.8  # obstacle ponctuel

        result_no_buf = compute_obstacles(roughness, threshold_m=0.4, buffer_m=0.0, resolution_m=RES, nodata=NODATA)
        result_buf = compute_obstacles(roughness, threshold_m=0.4, buffer_m=5.0, resolution_m=RES, nodata=NODATA)

        n_obstacle_no_buf = int(np.sum(result_no_buf == 1.0))
        n_obstacle_buf = int(np.sum(result_buf == 1.0))
        assert n_obstacle_buf > n_obstacle_no_buf, (
            f"Tampon devrait agrandir la zone : {n_obstacle_buf} vs {n_obstacle_no_buf}"
        )


class TestNodataPropagation:
    def test_nodata_propagation(self):
        """Les pixels nodata en entrée → nodata en sortie."""
        roughness = _make_roughness(50, center_val=0.0)
        roughness[10, 10] = NODATA
        result = compute_obstacles(roughness, threshold_m=0.4, buffer_m=0.0, resolution_m=RES, nodata=NODATA)
        assert result[10, 10] == NODATA


class TestBinaryOutput:
    def test_binary_output(self, dem_with_pit):
        """Seules les valeurs 0.0, 1.0 et nodata."""
        from marswalk_pipeline.derived.roughness import compute_roughness
        roughness = compute_roughness(dem_with_pit, window_m=3.0, resolution_m=RES, nodata=NODATA)
        result = compute_obstacles(roughness, threshold_m=0.4, buffer_m=2.0, resolution_m=RES, nodata=NODATA)
        allowed = {0.0, 1.0, NODATA}
        unique_vals = set(np.unique(result).tolist())
        assert unique_vals.issubset(allowed), f"Valeurs inattendues : {unique_vals - allowed}"
