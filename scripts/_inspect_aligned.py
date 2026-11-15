"""Quick inspection of aligned raster transforms and statistics."""
import sys
from pathlib import Path
import numpy as np
import rasterio

REPO = Path(__file__).resolve().parents[1]
ALIGNED = REPO / "data" / "work" / "jezero" / "aligned"

NODATA_FLOAT = -9999.0

print("=" * 80)
print("ALIGNED RASTERS — Transform + Statistics")
print("=" * 80)
for f in sorted(ALIGNED.glob("*.tif")):
    if ".bak" in f.name:
        continue
    with rasterio.open(f) as ds:
        tf = ds.transform
        band = ds.read(1).astype(np.float32)
        nd = ds.nodata if ds.nodata is not None else NODATA_FLOAT
        vm = np.isfinite(band) & ~np.isclose(band, nd, rtol=0, atol=1.0)
        n_valid = int(np.sum(vm))
        n_total = band.size
        pct = n_valid / n_total * 100

        stats = ""
        if n_valid > 0:
            vv = band[vm]
            stats = f" | min={np.min(vv):.2f}  max={np.max(vv):.2f}  mean={np.mean(vv):.2f}"

        print(f"{f.stem}")
        print(f"  transform.c (xmin) = {tf.c:.6f} m   (expected: -2500.000000)")
        print(f"  transform.f (ymax) = {tf.f:.6f} m   (expected: 1095798.085900)")
        print(f"  transform.a (res)  = {tf.a:.6f}")
        print(f"  transform.e (res)  = {tf.e:.6f}")
        print(f"  dims               = {ds.width} x {ds.height}")
        print(f"  bands              = {ds.count}")
        print(f"  dtype              = {ds.dtypes[0]}")
        print(f"  nodata             = {ds.nodata}")
        print(f"  valid              = {n_valid:,} / {n_total:,} = {pct:.2f}%{stats}")
        print()
