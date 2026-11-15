import rasterio

path = "./data/raw/jezero/JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first_dd.tif"

with rasterio.open(path) as src:
    print("\n========== MNT HiRISE JEZERO ==========")
    print("CRS          :", src.crs)
    print("Bounds       :", src.bounds)
    print("Resolution   :", src.res)
    print("Dimensions   :", src.width, "x", src.height)
    print("Bands        :", src.count)
    print("Data types   :", src.dtypes)
    print("NoData       :", src.nodata)
    print("Transform    :", src.transform)
    print("Driver       :", src.driver)
    print("======================================")