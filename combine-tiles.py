import os
import glob
from osgeo import gdal

YEAR = 2021
tiles_dir = "tiles"
merged_tif = f"final_rasters/{YEAR}.tif"
target_crs = "EPSG:32651"

os.makedirs(os.path.dirname(merged_tif), exist_ok=True)

tif_files = glob.glob(os.path.join(tiles_dir, "*.tif"))

if not tif_files:
    raise FileNotFoundError(f"No .tif files found in {tiles_dir}")

print(f"🔍 Found {len(tif_files)} tiles")

for tif in tif_files:
    ds = gdal.Open(tif)
    proj = ds.GetProjection()
    gt = ds.GetGeoTransform()
    res_x, res_y = gt[1], abs(gt[5])  # pixel size
    print(f"🗂 {os.path.basename(tif)}")
    print(f"   CRS: {proj.split()[0]}")
    print(f"   Resolution: {res_x} x {res_y} meters")
    print(f"   Size: {ds.RasterXSize} x {ds.RasterYSize} pixels")
    ds = None

print("\n🚀 Building VRT mosaic...")
vrt_path = "temp/temp.vrt"
gdal.BuildVRT(vrt_path, tif_files)
print(f"✅ VRT built: {vrt_path}")

print("🚀 Translating VRT to GeoTIFF...")
gdal.Translate(
    merged_tif,
    vrt_path,
    format="GTiff",
    creationOptions=["COMPRESS=LZW", "BIGTIFF=YES"],
)
print(f"✅ Merged mosaic saved as {merged_tif}")

os.remove("temp/temp.vrt")

print(f"✅ Deleted temporary VRT")
