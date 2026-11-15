"""Tests de la couche dérivée : radio_coverage."""

from __future__ import annotations

import numpy as np

from marswalk_pipeline.derived.radio_coverage import compute_radio_coverage

NODATA = -9999.0
RES = 1.0


class TestFlatAllVisible:
    def test_flat_all_visible(self) -> None:
        """DEM plat → tout visible depuis l'habitat."""
        size = 50
        dem = np.full((size, size), -2500.0, dtype=np.float32)
        hab = (size // 2, size // 2)
        result = compute_radio_coverage(
            dem, hab, antenna_height_m=3.0, resolution_m=RES, nodata=NODATA
        )
        valid = result != NODATA
        assert valid.any()
        assert np.all(result[valid] == 1.0), (
            f"DEM plat devrait rendre tout visible, {np.sum(result[valid] == 0.0)} pixels en ombre"
        )


class TestBehindHillInvisible:
    def test_behind_hill_invisible(self) -> None:
        """Obstacle derrière une colline → 0."""
        size = 100
        dem = np.full((size, size), -2500.0, dtype=np.float32)
        hab = (50, 10)  # habitat à gauche

        # Colline entre l'habitat et la cible
        dem[45:55, 30:35] = -2440.0  # +60m de relief

        result = compute_radio_coverage(
            dem, hab, antenna_height_m=3.0, resolution_m=RES, nodata=NODATA, n_angles=3600
        )

        # Les pixels très loin derrière la colline doivent être en ombre
        far_behind = result[48:52, 60:70]
        valid = far_behind != NODATA
        if valid.any():
            n_shadow = int(np.sum(far_behind[valid] == 0.0))
            assert n_shadow > 0, "Pixels derrière la colline devraient être en ombre"


class TestHabitatItselfVisible:
    def test_habitat_itself_visible(self) -> None:
        """Le pixel de l'habitat → 1."""
        size = 50
        dem = np.full((size, size), -2500.0, dtype=np.float32)
        hab = (25, 25)
        result = compute_radio_coverage(
            dem, hab, antenna_height_m=3.0, resolution_m=RES, nodata=NODATA
        )
        assert result[hab[0], hab[1]] == 1.0, "L'habitat lui-même doit être visible"


class TestNodataPropagation:
    def test_nodata_propagation(self) -> None:
        """Pixels nodata en entrée → nodata en sortie."""
        size = 50
        dem = np.full((size, size), -2500.0, dtype=np.float32)
        dem[10, 10] = NODATA
        hab = (25, 25)
        result = compute_radio_coverage(
            dem, hab, antenna_height_m=3.0, resolution_m=RES, nodata=NODATA
        )
        assert result[10, 10] == NODATA


class TestBinaryOutput:
    def test_binary_output(self) -> None:
        """Seules les valeurs 0.0, 1.0 et nodata."""
        size = 50
        dem = np.full((size, size), -2500.0, dtype=np.float32)
        dem[10, 10] = NODATA
        hab = (25, 25)
        result = compute_radio_coverage(
            dem, hab, antenna_height_m=3.0, resolution_m=RES, nodata=NODATA
        )
        allowed = {0.0, 1.0, NODATA}
        unique_vals = set(np.unique(result).tolist())
        assert unique_vals.issubset(allowed), f"Valeurs inattendues : {unique_vals - allowed}"


def test_rover_position_for_the_radio_relay() -> None:
    """Case du rover relais : lue en lon/lat, ignorée hors de la grille."""
    from rasterio.transform import from_origin

    from marswalk_pipeline.derived import _rover_px

    transform = from_origin(-50.0, 50.0, 1.0, 1.0)
    cfg = {"analysis_crs": "+proj=eqc +lat_ts=0 +lon_0=0 +R=3396190 +units=m +no_defs"}
    assert _rover_px({**cfg, "rover": None}, transform, 1.0, (100, 100)) is None
    lon = 10.0 / 3396190.0 * 180.0 / np.pi  # 10 m à l'est du centre
    row_col = _rover_px({**cfg, "rover": {"lon": lon, "lat": 0.0}}, transform, 1.0, (100, 100))
    assert row_col == (50, 60)
    far = _rover_px({**cfg, "rover": [1.0, 1.0]}, transform, 1.0, (100, 100))
    assert far is None  # hors grille : pas de relais, pas de repli au centre
