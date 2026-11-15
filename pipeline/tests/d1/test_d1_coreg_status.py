"""Statut du recalage jugé en pixels natifs de chaque couche (D1)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
import rasterio.transform

from marswalk_pipeline import coreg
from marswalk_pipeline.coreg import CoregResult, coregister, write_coreg_report

CRS = "+proj=eqc +lat_ts=18.4446 +lon_0=77.4502 +R=3396190 +units=m +no_defs"


def _raster(path: Path) -> None:
    data = np.random.default_rng(0).random((64, 64)).astype(np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=64,
        width=64,
        count=1,
        dtype="float32",
        crs=CRS,
        transform=rasterio.transform.from_origin(0.0, 64.0, 1.0, 1.0),
    ) as dst:
        dst.write(data, 1)


@pytest.fixture
def aligned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for layer in ("hirise_vis", "thermal_inertia"):
        _raster(tmp_path / f"{layer}.tif")
    # Résidu de 12,5 m après un décalage de (3, 4) m, comme THEMIS sur Jezero.
    monkeypatch.setattr(
        coreg, "_find_shift_subpixel", lambda *a, **k: (3.0, 4.0, 12.5, [12.5, 12.5])
    )
    return tmp_path


def test_residual_judged_in_native_pixels(aligned: Path) -> None:
    [r] = coregister(aligned, layers_to_coreg=("thermal_inertia",))
    assert r.status == "ok"  # 12,5 m pour des pixels THEMIS de 100 m
    assert r.residual_px == pytest.approx(0.125)
    assert "px de 100 m" in r.note


def test_native_resolution_override(aligned: Path) -> None:
    [r] = coregister(
        aligned, layers_to_coreg=("thermal_inertia",), native_res_m={"thermal_inertia": 6.0}
    )
    assert r.status == "degraded"
    assert r.residual_px == pytest.approx(12.5 / 6.0)


def test_report_shows_residual_in_pixels(tmp_path: Path) -> None:
    res = [CoregResult(layer_id="ctx_vis", residual_m=2.95, residual_px=0.49, n_tie_points=25)]
    path = write_coreg_report(tmp_path, [], res, site_id="test")
    assert "| 2.95 | 0.49 | 25 | ok |" in path.read_text("utf-8")
