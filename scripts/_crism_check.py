"""Detailed CRISM check."""
import numpy as np
import rasterio
from pathlib import Path

p = Path(r"C:\Users\casanova\Desktop\work\marswalk\data\work\jezero\aligned\crism_minerals.tif")
with rasterio.open(p) as ds:
    bands = ds.read()  # shape (3, H, W) uint8
    nd = ds.nodata
    print(f"nodata declared: {nd}")
    print(f"shape: {bands.shape}")
    print(f"dtype: {bands.dtype}")

nodata_all_zero = (bands[0] == 0) & (bands[1] == 0) & (bands[2] == 0)
n_all_zero = int(nodata_all_zero.sum())
n_total = bands[0].size
print(f"All-zero (black) pixels: {n_all_zero} / {n_total} = {n_all_zero/n_total*100:.2f}%")
print(f"Non-black pixels: {n_total - n_all_zero} = {(n_total-n_all_zero)/n_total*100:.2f}%")

# Check band 1 individually
b1 = bands[0]
print(f"Band 1: zeros={int((b1==0).sum())}  nonzero={int((b1>0).sum())}")
print(f"Band 1 range: [{int(b1.min())}, {int(b1.max())}]")

# What does the validation script compute?
# valid_mask uses band 1 only: np.isclose(band, nd) where nd=0.0
# band = ds.read(1).astype(float32)
# nd = 0.0
# vm = isfinite & ~isclose(band, 0.0, atol=1.0)
# That means anything >= 1 (since |band - 0| > 1 → not close)
b1f = b1.astype(np.float32)
vm = np.isfinite(b1f) & ~np.isclose(b1f, 0.0, rtol=0, atol=1.0)
print(f"Via validate_aligned_raster logic (band1): {int(vm.sum())} valid = {vm.sum()/vm.size*100:.2f}%")

# The scientific check says 100% because it misread bands
# Let me check what nonblack_pixels would be
# In the validate_d1.py script:
# nonblack = int(np.sum(np.any(bands_data > 0, axis=0)))
nonblack = int(np.sum(np.any(bands > 0, axis=0)))
print(f"Non-black (any band > 0): {nonblack} = {nonblack/n_total*100:.2f}%")
