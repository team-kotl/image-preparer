import ee
import geemap
from aoi import get_aoi_bbox
import folium

ee.Initialize(project="helical-sanctum-451207-m5")

AOI = ee.Geometry.Rectangle(get_aoi_bbox())
YEAR = 2021
START_DATE = f"{YEAR}-04-01"
END_DATE = f"{YEAR+1}-02-01"
CLOUD_FILTER = 80
CLD_PRB_THRESH = 50
NIR_DRK_THRESH = 0.15
CLD_PRJ_DIST = 1
BUFFER = 50

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


masked = imagery.map(add_cld_shdw_mask).map(apply_cld_shdw_mask)
cloudless = masked.median()
true_color = cloudless.select(["B4", "B3", "B2", "B8"])


# Define a method for displaying Earth Engine image tiles to a folium map.
def add_ee_layer(
    self, ee_image_object, vis_params, name, show=True, opacity=1, min_zoom=0
):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict["tile_fetcher"].url_format,
        attr='Map Data &copy; <a href="https://earthengine.google.com/">Google Earth Engine</a>',
        name=name,
        show=show,
        opacity=opacity,
        min_zoom=min_zoom,
        overlay=True,
        control=True,
    ).add_to(self)


# Add the Earth Engine layer method to folium.
folium.Map.add_ee_layer = add_ee_layer

center = AOI.centroid(10).coordinates().reverse().getInfo()
m = folium.Map(location=center, zoom_start=12)

# Add layers to the folium map.
m.add_ee_layer(
    cloudless,
    {"bands": ["B4", "B3", "B2"], "min": 0, "max": 2500, "gamma": 1.1},
    "S2 cloud-free mosaic",
    True,
    1,
    9,
)

# Add a layer control panel to the map.
m.add_child(folium.LayerControl())

# Display the map.
m.save(f"preview/{YEAR}_preview.html")


# Export to Google Drive
def make_grid(aoi, dx_km=50, dy_km=50):
    dx = dx_km / 111.32
    dy = dy_km / 110.57
    return geemap.fishnet(aoi, h_interval=dx, v_interval=dy)


grid = make_grid(AOI, dx_km=50, dy_km=50)
features = grid.toList(grid.size())
n = grid.size().getInfo()

for i in range(n):
    tile = ee.Feature(features.get(i)).geometry()
    count = masked.filterBounds(tile).size().getInfo()
    if count == 0:
        print(f"⚠ Tile {i} has no images, skipping.")
        continue
    task = ee.batch.Export.image.toDrive(
        image=true_color,
        description=f"{YEAR}_tile_{i}",
        folder="GEE_CAR_tiles",
        region=tile,
        scale=10,
        crs="EPSG:32651",
        maxPixels=1e13,
    )
    task.start()
    print(f"🚀 Started export for tile {i+1}/{n}")
