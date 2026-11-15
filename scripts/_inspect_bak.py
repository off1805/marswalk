"""Compare coreg-shifted rasters to their backups."""
import sys
from pathlib import Path
import numpy as np
import rasterio

ALIGNED = Path(r"C:\Users\casanova\Desktop\work\marswalk\data\work\jezero\aligned")

for bak in sorted(ALIGNED.glob("*.tif.bak")):
    tif = bak.with_suffix("")  # removes .bak → .tif
    layer = tif.stem

    print(f"=== {layer} ===")
    with rasterio.open(bak) as b_ds:
        b_tf = b_ds.transform
        print(f"  PRE-COREG  c={b_tf.c:.4f}  f={b_tf.f:.4f}")
    with rasterio.open(tif) as t_ds:
        t_tf = t_ds.transform
        print(f"  POST-COREG c={t_tf.c:.4f}  f={t_tf.f:.4f}")
    print(f"  SHIFT      dx={t_tf.c - b_tf.c:.4f} m  dy={t_tf.f - b_tf.f:.4f} m")
    print()
