import rasterio
import os
from pathlib import Path

data_dir = Path("data/raw/jezero")
files = sorted(data_dir.iterdir())

for f in files:
    size_mb = round(f.stat().st_size / 1024 / 1024, 2)
    print(f"\n{'='*70}")
    print(f"FILE   : {f.name}")
    print(f"SIZE   : {size_mb} MB")
    try:
        with rasterio.open(f) as src:
            print(f"DRIVER : {src.driver}")
            print(f"CRS    : {src.crs}")
            print(f"DIMS   : {src.width} x {src.height}  (bands={src.count})")
            print(f"DTYPE  : {src.dtypes}")
            print(f"NODATA : {src.nodata}")
            print(f"BOUNDS : left={src.bounds.left:.6f}, bottom={src.bounds.bottom:.6f}")
            print(f"         right={src.bounds.right:.6f}, top={src.bounds.top:.6f}")
            print(f"RES    : {src.res[0]:.8f} x {src.res[1]:.8f}")
            print(f"TRANSF : {src.transform}")
    except Exception as e:
        print(f"ERROR  : {e}")
