"""Classement des cubes CRISM MTRDR en carte de minéraux (D1), sur données synthétiques."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
import rasterio.transform

from marswalk_pipeline.ingest import (
    CRISM_CLAY_CARB,
    CRISM_OLIVINE,
    _crism_band_names,
    _is_crism_summary_cube,
    classify_crism_summary,
    ingest_layer,
)

CRS = "+proj=eqc +lat_ts=18.4446 +lon_0=77.4502 +R=3396190 +units=m +no_defs"
NAMES = ["R770", "OLINDEX3", "D2300", "MIN2295_2480", "MIN2345_2537", "BD2500_2"]


def _cube(path: Path, values: dict[str, np.ndarray], describe: bool = True) -> None:
    h, w = next(iter(values.values())).shape
    transform = rasterio.transform.from_origin(-40.0, 40.0, 20.0, 20.0)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=len(NAMES),
        dtype="float32",
        crs=CRS,
        transform=transform,
    ) as dst:
        for i, name in enumerate(NAMES, start=1):
            dst.write(values.get(name, np.zeros((h, w), np.float32)), i)
            if describe:
                dst.set_band_description(i, name)


def _values() -> dict[str, np.ndarray]:
    z = np.zeros((4, 4), np.float32)
    d2300, carb, oli = z.copy(), z.copy(), z.copy()
    d2300[0, 0] = 0.03  # argile
    carb[0, 1] = 0.02  # carbonate
    oli[1, 0] = 0.2  # olivine
    oli[0, 1] = 0.3  # olivine et carbonate : rangé en argiles et carbonates
    d2300[3, 3] = 65535.0  # pixel vide du MTRDR
    return {"D2300": d2300, "MIN2295_2480": carb, "OLINDEX3": oli}


def test_band_names_from_descriptions_and_envi_header(tmp_path: Path) -> None:
    described = tmp_path / "a.tif"
    _cube(described, _values())
    assert _crism_band_names(described) == NAMES
    assert _is_crism_summary_cube(described)

    bare = tmp_path / "b.tif"
    _cube(bare, _values(), describe=False)
    (tmp_path / "b.hdr").write_text(
        "ENVI\nband names = {\n " + ", ".join(NAMES[:3]) + ",\n " + ", ".join(NAMES[3:]) + "}\n",
        "utf-8",
    )
    assert _crism_band_names(bare) == NAMES


def test_classify_summary_cube(tmp_path: Path) -> None:
    src = tmp_path / "su.tif"
    _cube(src, _values())
    out = tmp_path / "classes.tif"
    counts = classify_crism_summary(src, out)
    with rasterio.open(out) as ds:
        classes = ds.read(1)
        assert ds.dtypes[0] == "uint8" and ds.count == 1
    assert classes[0, 0] == CRISM_CLAY_CARB
    assert classes[0, 1] == CRISM_CLAY_CARB
    assert classes[1, 0] == CRISM_OLIVINE
    assert classes[3, 3] == 0
    assert counts == {"clay_carb": 2, "olivine": 1, "pixels": 16}


def test_ingest_layer_writes_single_band_class_map(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    _cube(raw / "su.tif", _values())
    aligned = tmp_path / "aligned"
    transform = rasterio.transform.from_origin(-40.0, 40.0, 10.0, 10.0)
    result = ingest_layer(
        "crism_minerals",
        {},
        {"crism_minerals": {"file": "su.tif"}},
        raw,
        aligned,
        CRS,
        transform,
        8,
        8,
    )
    assert result.status == "ok"
    assert "classé depuis MTRDR" in result.note
    with rasterio.open(aligned / "crism_minerals.tif") as ds:
        assert ds.count == 1 and ds.dtypes[0] == "uint8"
        assert set(np.unique(ds.read(1))) <= {0, CRISM_CLAY_CARB, CRISM_OLIVINE}
    assert not (aligned / "crism_minerals_classes_src.tif").exists()
