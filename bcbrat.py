# try and generate a very simple BRAT project

import logging
import sys
import subprocess

import bcdata
#import requests
#import rsxml

log = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s:%(levelname)s:%(name)s: %(message)s"


def configure_logging(verbosity):
    log_level = max(10, 30 - 10 * verbosity)
    logging.basicConfig(stream=sys.stderr, level=log_level, format=LOG_FORMAT)


configure_logging(1)

# get watershed boundary
log.info("downloading watershed boundary")
wsd = bcdata.get_data(
    "WHSE_BASEMAPPING.FWA_ASSESSMENT_WATERSHEDS_POLY",
    query="WATERSHED_FEATURE_ID=2904",
    as_gdf=True,
    crs="EPSG:3005",
)
bounds = list(wsd.total_bounds)

# get dem (automatically saved to dem.tif)
log.info("downloading DEM")
dem = bcdata.get_dem(bounds)

# generate simple hillshade with gdaldem
log.info("generating hillshade")
subprocess.run(
    [
        "gdaldem",
        "hillshade",
        "dem.tif",
        "hillshade.tif",
    ]
)

# download hydrology


# download vector sources that can be directly extracted via bcdata
for layer in [
    "WHSE_FOREST_VEGETATION.VEG_COMP_LYR_R1_POLY",
    "WHSE_BASEMAPPING.DRA_DGTL_ROAD_ATLAS_MPAR_SP",
    "WHSE_FOREST_VEGETATION.BEC_BIOGEOCLIMATIC_POLY",
    "WHSE_BASEMAPPING.GBA_RAILWAY_TRACKS_SP"
]:
    log.info(f"downloading {layer}")
    df = bcdata.get_data(layer, as_gdf=True, crs="EPSG:3005", bounds=bounds, bounds_crs="EPSG:3005")
    # save as individual geopackage (if data present)
    if len(df) > 0:
        layername = layer.split(".")[1].lower()
        filename = layername+".gpkg"
        log.info(f"saving {layer} to {filename}")
        df.to_file(filename, driver="GPKG", layer=layername)
