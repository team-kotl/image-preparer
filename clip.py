import os
from osgeo import gdal

YEAR = 2021

input_raster = f"final_rasters/{YEAR}.tif"
mask_vector = "boundary/Municipalities.shp"
output_raster = f"clipped_rasters/{YEAR}.tif"

# Make sure output folder exists
os.makedirs(os.path.dirname(output_raster), exist_ok=True)

# gdal.Warp does the clipping with a cutline
gdal.Warp(
    destNameOrDestDS=output_raster,
    srcDSOrSrcDSTab=input_raster,
    cutlineDSName=mask_vector,
    cropToCutline=True,
    dstNodata=None,
    multithread=True,
)

print(f"✅ Clipped raster saved to {output_raster}")

os.remove(f"final_rasters/{YEAR}.tif")

print(f"✅ Removed unclipped raster")
