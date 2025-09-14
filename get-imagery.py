import sys
import ee
import geemap
from aoi import get_aoi_bbox

ee.Initialize(project="helical-sanctum-451207-m5")

AOI = ee.Geometry.Rectangle(get_aoi_bbox())
YEAR = None
START_DATE = None
END_DATE = None
# YEAR = 2018
# START_DATE = f"2016-04-08"
# END_DATE = f"2018-12-31"
CLOUD_FILTER = 100
CLD_PRB_THRESH = 50
NIR_DRK_THRESH = 0.15
CLD_PRJ_DIST = 1
BUFFER = 50


def add_cloud_bands(img):
    # Get s2cloudless image, subset the probability band.
    cld_prb = ee.Image(img.get("s2cloudless")).select("probability")

    # Condition s2cloudless by the probability threshold value.
    is_cloud = cld_prb.gt(CLD_PRB_THRESH).rename("clouds")

    # Add the cloud probability layer and cloud mask as image bands.
    return img.addBands(ee.Image([cld_prb, is_cloud]))


def add_shadow_bands(img):
    # Identify water pixels from the SCL band.
    not_water = img.select("SCL").neq(6)

    # Identify dark NIR pixels that are not water (potential cloud shadow pixels).
    SR_BAND_SCALE = 1e4
    dark_pixels = (
        img.select("B8")
        .lt(NIR_DRK_THRESH * SR_BAND_SCALE)
        .multiply(not_water)
        .rename("dark_pixels")
    )

    # Determine the direction to project cloud shadow from clouds (assumes UTM projection).
    shadow_azimuth = ee.Number(90).subtract(
        ee.Number(img.get("MEAN_SOLAR_AZIMUTH_ANGLE"))
    )

    # Project shadows from clouds for the distance specified by the CLD_PRJ_DIST input.
    cld_proj = (
        img.select("clouds")
        .directionalDistanceTransform(shadow_azimuth, CLD_PRJ_DIST * 10)
        .reproject(**{"crs": img.select(0).projection(), "scale": 100})
        .select("distance")
        .mask()
        .rename("cloud_transform")
    )

    # Identify the intersection of dark pixels with cloud shadow projection.
    shadows = cld_proj.multiply(dark_pixels).rename("shadows")

    # Add dark pixels, cloud projection, and identified shadows as image bands.
    return img.addBands(ee.Image([dark_pixels, cld_proj, shadows]))


def add_cld_shdw_mask(img):
    # Add cloud component bands.
    img_cloud = add_cloud_bands(img)

    # Add cloud shadow component bands.
    img_cloud_shadow = add_shadow_bands(img_cloud)

    # Combine cloud and shadow mask, set cloud and shadow as value 1, else 0.
    is_cld_shdw = (
        img_cloud_shadow.select("clouds").add(img_cloud_shadow.select("shadows")).gt(0)
    )

    # Remove small cloud-shadow patches and dilate remaining pixels by BUFFER input.
    # 20 m scale is for speed, and assumes clouds don't require 10 m precision.
    is_cld_shdw = (
        is_cld_shdw.focalMin(2)
        .focalMax(BUFFER * 2 / 20)
        .reproject(**{"crs": img.select([0]).projection(), "scale": 20})
        .rename("cloudmask")
    )

    # Add the final cloud-shadow mask to the image.
    return img_cloud_shadow.addBands(is_cld_shdw)


def apply_cld_shdw_mask(img):
    # Subset the cloudmask band and invert it so clouds/shadow are 0, else 1.
    not_cld_shdw = img.select("cloudmask").Not()

    # Subset reflectance bands and update their masks, return the result.
    return img.select("B.*").updateMask(not_cld_shdw)


def make_grid(aoi, dx_km=10, dy_km=10):
    dx = dx_km / 111.32
    dy = dy_km / 110.57
    return geemap.fishnet(aoi, h_interval=dx, v_interval=dy)


def run_pipeline():
    s2_sr_col = (
        ee.ImageCollection("COPERNICUS/S2_SR")
        .filterBounds(AOI)
        .filterDate(START_DATE, END_DATE)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", CLOUD_FILTER))
    )

    s2_cloudless_col = (
        ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY")
        .filterBounds(AOI)
        .filterDate(START_DATE, END_DATE)
    )

    imagery = ee.ImageCollection(
        ee.Join.saveFirst("s2cloudless").apply(
            **{
                "primary": s2_sr_col,
                "secondary": s2_cloudless_col,
                "condition": ee.Filter.equals(
                    **{"leftField": "system:index", "rightField": "system:index"}
                ),
            }
        )
    )

    masked = imagery.map(add_cld_shdw_mask).map(apply_cld_shdw_mask)
    cloudless = masked.median()
    true_color = cloudless.select(["B4", "B3", "B2", "B8"])

    grid = make_grid(AOI, dx_km=10, dy_km=10)
    features = grid.toList(grid.size())
    n = grid.size().getInfo()
    from tqdm import tqdm

    # Local export instead of Google Drive
    for i in tqdm(range(n), desc="Downloading tiles"):
        tile = ee.Feature(features.get(i)).geometry()
        count = masked.filterBounds(tile).size().getInfo()
        if count == 0:
            print(f"⚠ Tile {i} has no images, skipping.")
            continue
        out_tif = f"tiles/{YEAR}_tile_{i}.tif"
        geemap.ee_export_image(
            true_color.clip(tile),
            filename=out_tif,
            scale=10,
            crs="EPSG:32651",
            region=tile,
        )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        YEAR = int(arg)
        START_DATE = f"{YEAR}-04-01"
        END_DATE = f"{YEAR+1}-02-01"
        run_pipeline()
    else:
        print("No year provided.")
