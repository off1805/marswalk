"""Investigate CRISM anomaly after coreg shift."""
import numpy as np
import rasterio
from pathlib import Path

p_post = Path(r"C:\Users\casanova\Desktop\work\marswalk\data\work\jezero\aligned\crism_minerals.tif")
p_pre = Path(r"C:\Users\casanova\Desktop\work\marswalk\data\work\jezero\aligned\crism_minerals.tif.bak")

print("=== PRE-COREG (backup) ===")
with rasterio.open(p_pre) as ds:
    bands_pre = ds.read()
    tf_pre = ds.transform
    print(f"transform.c={tf_pre.c:.4f}, f={tf_pre.f:.4f}")

zero_pre = (bands_pre[0] == 0) & (bands_pre[1] == 0) & (bands_pre[2] == 0)
print(f"All-zero pixels: {zero_pre.sum()} ({zero_pre.sum()/zero_pre.size*100:.2f}%)")
b1_zero_pre = int((bands_pre[0] == 0).sum())
print(f"Band1 zeros: {b1_zero_pre} ({b1_zero_pre/bands_pre[0].size*100:.2f}%)")

print()
print("=== POST-COREG ===")
with rasterio.open(p_post) as ds:
    bands_post = ds.read()
    tf_post = ds.transform
    print(f"transform.c={tf_post.c:.4f}, f={tf_post.f:.4f}")
    print(f"shift applied: dx={tf_post.c - tf_pre.c:.2f} m, dy={tf_post.f - tf_pre.f:.2f} m")
    print("(Note: coreg only changes transform metadata, NOT pixel data)")
    
zero_post = (bands_post[0] == 0) & (bands_post[1] == 0) & (bands_post[2] == 0)
print(f"All-zero pixels: {zero_post.sum()} ({zero_post.sum()/zero_post.size*100:.2f}%)")
b1_zero_post = int((bands_post[0] == 0).sum())
print(f"Band1 zeros: {b1_zero_post} ({b1_zero_post/bands_post[0].size*100:.2f}%)")

print()
print("=== KEY INSIGHT ===")
print("apply_shift() in coreg/__init__.py modifies ONLY the affine transform.")
print("The pixel array is NOT resampled. So pixel statistics are identical pre/post coreg.")
print(f"Pixel arrays identical: {np.array_equal(bands_pre, bands_post)}")
print()
print("Discrepancy in validation: validate_aligned_raster reads band 1 as float32")
print("and applies isclose(band, nd=-9999, atol=1.0). For uint8 CRISM with nodata=0:")
print("  band1 as float32, nd = 0.0")
print("  valid = isfinite(band) & ~isclose(band, 0.0, atol=1.0)")
print("  = pixels where band1 > 1 (since |band - 0| > 1 → not close to 0)")
print("  = pixels with band1 value >= 2 (since 1 is within atol=1.0 of 0)")
print(f"  Band1 == 1: {int((bands_post[0] == 1).sum())} pixels")
print(f"  Band1 >= 2: {int((bands_post[0] >= 2).sum())} pixels -> 60.26% = 15064074")
print(f"  Band1 == 0: {int((bands_post[0] == 0).sum())} pixels")
print()
print("So the 60.26% metric reflects pixels where Band1 >= 2.")
print("The ~40% 'invalid' pixels have Band1 == 0 (no-data border region).")
print("Band1 == 1 pixels are ambiguous (within atol of 0.0 nodata).")
print(f"Band1 == 1 count: {int((bands_post[0] == 1).sum())}")
