# try and generate a very simple BRAT project

import logging
import sys
import subprocess
from urllib.parse import urlencode

import bcdata
import geopandas as gpd
import pandas as pd
import rasterio.warp
from shapely import wkb

# import rsxml

log = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s:%(levelname)s:%(name)s: %(message)s"


def configure_logging(verbosity):
    log_level = max(10, 30 - 10 * verbosity)
    logging.basicConfig(stream=sys.stderr, level=log_level, format=LOG_FORMAT)


def warp_bounds(bounds, crs_source="EPSG:3005", crs_target="EPSG:4326"):
    xs = bounds[::2]
    ys = bounds[1::2]
    xs, ys = rasterio.warp.transform(crs_source, crs_target, xs, ys)
    xs = [round(v, 5) for v in xs]
    ys = [round(v, 5) for v in ys]
    result = [0] * len(bounds)
    result[::2] = xs
    result[1::2] = ys
    return result


def define_fwa_request(table, bounds):
    fwa_url = "https://features.hillcrestgeo.ca/fwa/collections/"
    param = {"bbox": ",".join([str(b) for b in bounds])}
    url = fwa_url + f"{table}/" + "items.json?" + urlencode(param, doseq=True)
    log.debug(url)
    return url


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
bounds_ll = warp_bounds(bounds)

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

# download hydrology, write to single gpkd
streams = gpd.read_file(
    define_fwa_request("whse_basemapping.fwa_streams_vw", bounds_ll)
)
# make streams 2d
# https://gist.github.com/rmania/8c88377a5c902dfbc134795a7af538d8?permalink_comment_id=4252276#gistcomment-4252276
_drop_z = lambda geom: wkb.loads(wkb.dumps(geom, output_dimension=2))
streams.geometry = streams.geometry.transform(_drop_z)
# convert upstream area to km2
streams["totdasqkm"] = streams["upstream_area_ha"] * .01

if len(streams) > 0:
    streams.to_file("hydrology.gpkg", driver="GPKG", layer="flow_lines")

rivers = gpd.read_file(
    define_fwa_request("whse_basemapping.fwa_rivers_poly", bounds_ll)
)
if len(rivers) > 0:
    rivers.to_file("hydrology.gpkg", driver="GPKG", layer="flow_areas")

# combine lakes and reservoirs into a waterbody layer
lakes = gpd.read_file(define_fwa_request("whse_basemapping.fwa_lakes_poly", bounds_ll))
reservoirs = gpd.read_file(
    define_fwa_request("whse_basemapping.fwa_manmade_waterbodies_poly", bounds_ll)
)
waterbodies = gpd.GeoDataFrame()
if len(lakes) > 0 and len(reservoirs) == 0:
    waterbodies = lakes
elif len(lakes) == 0 and len(reservoirs) > 0:
    waterbodies = reservoirs
elif len(lakes) > 0 and len(reservoirs) > 0:
    waterbodies = pd.concat([lakes, reservoirs])
if len(waterbodies) > 0:
    waterbodies.to_file("hydrology.gpkg", driver="GPKG", layer="waterbodies")

# write watershed boundary
wsd.to_file("hydrology.gpkg", driver="GPKG", layer="watershed")

# download vector sources that can be directly extracted via bcdata
for layer in [
    "WHSE_FOREST_VEGETATION.VEG_COMP_LYR_R1_POLY",
    "WHSE_BASEMAPPING.DRA_DGTL_ROAD_ATLAS_MPAR_SP",
    "WHSE_FOREST_VEGETATION.BEC_BIOGEOCLIMATIC_POLY",
    "WHSE_BASEMAPPING.GBA_RAILWAY_TRACKS_SP",
]:
    log.info(f"downloading {layer}")
    df = bcdata.get_data(
        layer, as_gdf=True, crs="EPSG:3005", bounds=bounds, bounds_crs="EPSG:3005"
    )
    # save as individual geopackage (if data present)
    if len(df) > 0:
        layername = layer.split(".")[1].lower()
        filename = layername + ".gpkg"
        log.info(f"saving {layer} to {filename}")
        df.to_file(filename, driver="GPKG", layer=layername)


# create brat package
