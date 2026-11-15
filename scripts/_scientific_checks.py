"""Scientific consistency checks for D1 aligned rasters."""
import sys
from pathlib import Path
import numpy as np
import rasterio

ALIGNED = Path(r"C:\Users\casanova\Desktop\work\marswalk\data\work\jezero\aligned")
NODATA = -9999.0

print("=" * 70)
print("SCIENTIFIC CONSISTENCY CHECKS — D1 Jezero")
print("=" * 70)
print()

# ---- DEM vs MOLA cross-check ----
print("1. DEM cross-check (HiRISE DTM vs MOLA)")
with rasterio.open(ALIGNED / "dem.tif") as ds:
    h = ds.read(1).astype(np.float32)
    vm = np.isfinite(h) & ~np.isclose(h, NODATA, rtol=0, atol=1.0)
    hv = h[vm]
with rasterio.open(ALIGNED / "dem_mola.tif") as ds:
    m = ds.read(1).astype(np.float32)
    vmm = np.isfinite(m) & ~np.isclose(m, NODATA, rtol=0, atol=1.0)
    mv = m[vmm]
print(f"   HiRISE DTM  : mean={hv.mean():.1f} m  std={hv.std():.1f} m  [{hv.min():.1f}, {hv.max():.1f}]")
print(f"   MOLA DEM    : mean={mv.mean():.1f} m  std={mv.std():.1f} m  [{mv.min():.1f}, {mv.max():.1f}]")
print(f"   Difference  : mean bias = {hv.mean() - mv.mean():.2f} m")
print(f"   Expected    : Jezero floor ~-2500 m (MOLA reference)")
print()

# ---- Thermal Inertia range check ----
print("2. Thermal Inertia physical range check")
with rasterio.open(ALIGNED / "thermal_inertia.tif") as ds:
    ti = ds.read(1).astype(np.float32)
    nd = ds.nodata if ds.nodata is not None else NODATA
    vm = np.isfinite(ti) & ~np.isclose(ti, nd, rtol=0, atol=1.0)
    tiv = ti[vm]
zeros = int(np.sum(tiv == 0.0))
negatives = int(np.sum(tiv < 0))
print(f"   Range       : [{tiv.min():.2f}, {tiv.max():.2f}] J m-2 K-1 s-1/2")
print(f"   Mean ± std  : {tiv.mean():.2f} ± {tiv.std():.2f}")
print(f"   Zeros       : {zeros} (expected 0 — NoData correctly masked)")
print(f"   Negatives   : {negatives} (expected 0 — TI is always positive)")
print(f"   Coverage    : {vm.sum()} px / {vm.size} px ({vm.sum()/vm.size*100:.1f}%)")
print(f"   Expected    : basalt/sediment Jezero ~200-350 TIU typical")
print()

# ---- CRISM RGB range check ----
print("3. CRISM RGB range and coverage check")
with rasterio.open(ALIGNED / "crism_minerals.tif") as ds:
    bands = ds.read()  # 3 x H x W uint8
nodata_mask = (bands[0] == 0) & (bands[1] == 0) & (bands[2] == 0)
n_valid = int((~nodata_mask).sum())
n_total = nodata_mask.size
for i, name in enumerate(["R", "G", "B"]):
    b = bands[i]
    bv = b[~nodata_mask]
    print(f"   Band {name}      : [{int(bv.min())}, {int(bv.max())}]  mean={bv.mean():.1f}")
print(f"   Coverage    : {n_valid} px / {n_total} px ({n_valid/n_total*100:.1f}%)")
print(f"   NoData      : RGB=[0,0,0] — nearest-neighbour applied")
print()

# ---- HiRISE ortho range check ----
print("4. HiRISE Ortho radiometry check")
with rasterio.open(ALIGNED / "hirise_vis.tif") as ds:
    vis = ds.read(1).astype(np.float32)
    nd = ds.nodata if ds.nodata is not None else NODATA
    vm = np.isfinite(vis) & ~np.isclose(vis, nd, rtol=0, atol=1.0)
    vv = vis[vm]
print(f"   Range       : [{int(vv.min())}, {int(vv.max())}]")
print(f"   Mean ± std  : {vv.mean():.1f} ± {vv.std():.1f}")
print(f"   Coverage    : {vm.sum()} / {vm.size} = {vm.sum()/vm.size*100:.1f}%")
print(f"   Note        : uint8 source, bilinear resampled to float32")
print()

# ---- CTX ortho ----
print("5. CTX Ortho radiometry check (post-coreg +1m shift)")
with rasterio.open(ALIGNED / "ctx_vis.tif") as ds:
    ctx = ds.read(1).astype(np.float32)
    nd = ds.nodata if ds.nodata is not None else NODATA
    vm = np.isfinite(ctx) & ~np.isclose(ctx, nd, rtol=0, atol=1.0)
    cv = ctx[vm]
print(f"   Range       : [{int(cv.min())}, {int(cv.max())}]")
print(f"   Mean ± std  : {cv.mean():.1f} ± {cv.std():.1f}")
print(f"   Coverage    : {vm.sum()} / {vm.size} = {vm.sum()/vm.size*100:.1f}%")
print()

# ---- DEM continuity check (no large jumps) ----
print("6. DEM spatial continuity check")
with rasterio.open(ALIGNED / "dem.tif") as ds:
    dem = ds.read(1).astype(np.float32)
    nd = ds.nodata if ds.nodata is not None else NODATA
    vm = np.isfinite(dem) & ~np.isclose(dem, nd, rtol=0, atol=1.0)
dem_valid = np.where(vm, dem, np.nan)
# Gradient in X and Y (m per pixel = m/m since 1m/px)
gx = np.abs(np.diff(dem_valid, axis=1))
gy = np.abs(np.diff(dem_valid, axis=0))
gx_valid = gx[np.isfinite(gx)]
gy_valid = gy[np.isfinite(gy)]
print(f"   Max X-gradient : {gx_valid.max():.2f} m/px")
print(f"   Max Y-gradient : {gy_valid.max():.2f} m/px")
print(f"   P99 gradient   : X={np.percentile(gx_valid, 99):.2f}  Y={np.percentile(gy_valid, 99):.2f} m/px")
print(f"   Note           : steep cliffs in Jezero crater can be ~10-30 m/m vertical")
# Identify extreme jumps (>100m/px would be artifact)
n_extreme = int(np.sum(gx_valid > 100)) + int(np.sum(gy_valid > 100))
print(f"   Jumps > 100 m/px: {n_extreme} (expected 0 for artifact-free DEM)")
print()

print("=" * 70)
print("All checks complete.")
