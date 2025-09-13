import os
import glob
from osgeo import gdal

# -----------------------
# Configuration
# -----------------------
SOURCE_TIF = "2019.tif"

BOUNDARIES = {
    "municipality": "boundaries/municipalities",
    "province": "boundaries/provinces"
}

OUTPUT_DIR = "separated"


def clip_with_gpkgs(boundary_type, base_dir):
    if boundary_type == "municipality":
        # Walk through nested province folders
        for province in os.listdir(base_dir):
            province_dir = os.path.join(base_dir, province)
            if not os.path.isdir(province_dir):
                continue

            out_province_dir = os.path.join(OUTPUT_DIR, boundary_type, province)
            os.makedirs(out_province_dir, exist_ok=True)

            # Find all GPKGs in province folder
            gpkg_files = glob.glob(os.path.join(province_dir, "*.gpkg"))

            for gpkg in gpkg_files:
                name = os.path.splitext(os.path.basename(gpkg))[0]
                out_tif = os.path.join(out_province_dir, f"{name}.tif")

                gdal.Warp(
                    out_tif,
                    SOURCE_TIF,
                    cutlineDSName=gpkg,
                    cropToCutline=True,
                    dstNodata=0
                )

                print(f"✔ Saved {out_tif}")

    elif boundary_type == "province":
        # Flat structure
        out_dir = os.path.join(OUTPUT_DIR, boundary_type)
        os.makedirs(out_dir, exist_ok=True)

        gpkg_files = glob.glob(os.path.join(base_dir, "*.gpkg"))

        for gpkg in gpkg_files:
            name = os.path.splitext(os.path.basename(gpkg))[0]
            out_tif = os.path.join(out_dir, f"{name}.tif")

            gdal.Warp(
                out_tif,
                SOURCE_TIF,
                cutlineDSName=gpkg,
                cropToCutline=True,
                dstNodata=0
            )

            print(f"✔ Saved {out_tif}")


def main():
    for btype, path in BOUNDARIES.items():
        print(f"\n--- Processing {btype} ---")
        clip_with_gpkgs(btype, path)


if __name__ == "__main__":
    main()
