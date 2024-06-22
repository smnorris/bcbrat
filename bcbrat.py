from datetime import datetime
import getpass
import json
import os
import subprocess
from urllib.parse import urlencode

import bcdata
import click
from cligj import verbose_opt, quiet_opt
import geopandas as gpd
import jsonschema
import pandas as pd
import rsxml
from rsxml.project_xml import (
    BoundingBox,
    Coords,
    Dataset,
    Geopackage,
    GeoPackageDatasetTypes,
    GeopackageLayer,
    Meta,
    MetaData,
    Project,
    ProjectBounds,
    Realization,
)
from shapely import wkb

LOG = rsxml.Logger("Project")


def validate_config(config):
    # is json valid according to schema?
    with open("config.schema.json", "r") as f:
        schema = json.load(f)
    jsonschema.validate(instance=config, schema=schema)
    LOG.info("Config json is valid")


def define_fwa_request(table, bounds):
    fwa_url = "https://features.hillcrestgeo.ca/fwa/collections/"
    param = {"bbox": ",".join([str(b) for b in bounds])}
    url = fwa_url + f"{table}/" + "items.json?" + urlencode(param, doseq=True)
    return url


def build_project(config):
    """
    Create BC Brat project - datasets and xml - based on provided config
    """
    wsd = bcdata.get_data(
        config["watershed_source"],
        query=config["watershed_query"],
        as_gdf=True,
        crs="EPSG:3005",
    )
    # lat/lon bounds are required, convert watershed gdf geographic coordinates
    wsd_ll = wsd.to_crs("EPSG:4326")
    bounds_ll = list(wsd_ll.total_bounds)
    centroid_ll = (wsd_ll.centroid.x[0], wsd_ll.centroid.y[0])

    # initialize the project object
    project = Project(
        name=config["project_name"],
        proj_path=os.path.join(config["out_path"], "project.rs.xml"),
        project_type="RSContextBC",
        description=config["project_description"],
        citation=config["project_citation"],
        bounds=ProjectBounds(
            centroid=Coords(centroid_ll[0], centroid_ll[1]),
            bounding_box=BoundingBox(
                bounds_ll[0], bounds_ll[1], bounds_ll[2], bounds_ll[3]
            ),
            filepath=os.path.join(config["out_path"], "project_bounds.geojson"),
        ),
        realizations=[
            Realization(
                xml_id="bcbrat",
                name=config["realization_name"],
                product_version="1.0.0",
                date_created=datetime.today(),
                summary=config["realization_summary"],
                description=config["realization_description"]
            )
        ],
    )
    # add project level metadata from config
    for meta in config["meta"]:
        project.meta_data.add_meta(meta["key"], meta["value"])

    # automatic meta
    project.meta_data.add_meta("date_created", datetime.today())
    project.meta_data.add_meta("user", getpass.getuser())
    project.meta_data.add_meta("script_path", os.path.realpath(__file__))

    # ========================
    # DEM/Hillshade
    # ========================
    LOG.info("downloading DEM")
    bounds = wsd.bounds
    bcdata.get_dem(bounds)  # automatically saved to dem.tif

    # compress the dem
    subprocess.run(
        [
            "gdal_translate",
            "dem.tif",
            "dem_compressed.tif",
            "-co",
            "COMPRESS=LZW"
        ]
    )
    # delete initial dem tiff
    os.unlink("dem.tif")
    os.rename("dem_compressed.tif", "dem.tif")

    realization = project.realizations[0]
    realization.datasets.append(
        Dataset(
            xml_id="dem",
            name="DEM",
            path="dem.tif",
            ds_type="DEM",
            ext_ref="",
            summary="25m DEM",
            description="25m DEM",
        )
    )

    # generate simple hillshade with gdaldem
    # modify to compress
    LOG.info("generating hillshade")
    subprocess.run(
        [
            "gdaldem",
            "hillshade",
            "dem.tif",
            "hillshade.tif",
            "-co",
            "COMPRESS=LZW"
        ]
    )

    realization.datasets.append(
        Dataset(
            xml_id="hillshade",
            name="Hillshade",
            path="hillshade.tif",
            ds_type="RASTER",
            ext_ref="",
            summary="25m hillshade",
            description="25m hillshade",
        )
    )

    # ========================
    # Hydrology
    # ========================
    # create hydrology geopackage
    wsd.to_file("hydrology.gpkg", driver="GPKG", layer="watershed")
    hydrology_layers = []
    hydrology_layers.append(
        GeopackageLayer(
            lyr_name="watershed",
            name="watershed",
            ds_type=GeoPackageDatasetTypes.VECTOR,
            summary="Watershed of interest",
            description=config["watershed_source"] + " WHERE " + config["watershed_query"],
            citation=config["watershed_citation"]
        )
    )

    url = define_fwa_request("whse_basemapping.fwa_streams_vw", bounds_ll)
    LOG.debug(url)
    streams = gpd.read_file(url)
    # make streams 2d
    # https://gist.github.com/rmania/8c88377a5c902dfbc134795a7af538d8?permalink_comment_id=4252276#gistcomment-4252276
    _drop_z = lambda geom: wkb.loads(wkb.dumps(geom, output_dimension=2))
    streams.geometry = streams.geometry.transform(_drop_z)
    # convert upstream area to km2
    streams["totdasqkm"] = streams["upstream_area_ha"] * 0.01

    if len(streams) > 0:
        streams.to_file("hydrology.gpkg", driver="GPKG", layer="flow_lines")
        hydrology_layers.append(
            GeopackageLayer(
                lyr_name="flow_lines",
                name="flow lines",
                ds_type=GeoPackageDatasetTypes.VECTOR,
                summary="FWA stream network flow lines",
                description="FWA stream network flow lines",
                citation="FWA citation",
                meta_data=MetaData(values=[Meta("Test", "Test Value")]),
            )
        )

    rivers = gpd.read_file(
        define_fwa_request("whse_basemapping.fwa_rivers_poly", bounds_ll)
    )
    if len(rivers) > 0:
        rivers.to_file("hydrology.gpkg", driver="GPKG", layer="flow_areas")
        hydrology_layers.append(
            GeopackageLayer(
                lyr_name="flow_areas",
                name="flow areas",
                ds_type=GeoPackageDatasetTypes.VECTOR,
                summary="FWA rivers",
                description="FWA rivers",
                citation="FWA citation",
                meta_data=MetaData(values=[Meta("Test", "Test Value")]),
            )
        )

    # combine lakes and reservoirs into a waterbody layer
    lakes = gpd.read_file(
        define_fwa_request("whse_basemapping.fwa_lakes_poly", bounds_ll)
    )
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
        hydrology_layers.append(
            GeopackageLayer(
                lyr_name="waterbodies",
                name="waterbodies",
                ds_type=GeoPackageDatasetTypes.VECTOR,
                summary="FWA lakes and reservoirs",
                description="FWA lakes and reservoirs",
                citation="FWA citation",
                meta_data=MetaData(values=[Meta("Test", "Test Value")]),
            )
        )

    # add the hydrology layers to the realization
    realization.datasets.append(
        Geopackage(
            xml_id="hydrology",
            name="hydrology",
            path="hydrology.gpkg",
            summary="Watershed boundary",
            description="Watershed boundary",
            citation="citation",
            meta_data=MetaData(values=[Meta("Test", "Test Value")]),
            layers=hydrology_layers,
        )
    )

    # ========================
    # Other layers from bcdata
    # ========================
    for layer in [
        "WHSE_FOREST_VEGETATION.VEG_COMP_LYR_R1_POLY",
        "WHSE_BASEMAPPING.DRA_DGTL_ROAD_ATLAS_MPAR_SP",
        "WHSE_FOREST_VEGETATION.BEC_BIOGEOCLIMATIC_POLY",
        "WHSE_BASEMAPPING.GBA_RAILWAY_TRACKS_SP",
    ]:
        LOG.info(f"downloading {layer}")
        df = bcdata.get_data(
            layer, as_gdf=True, crs="EPSG:3005", bounds=bounds, bounds_crs="EPSG:3005"
        )
        # save as individual geopackage (if data present)
        if len(df) > 0:
            layername = layer.split(".")[1].lower()
            filename = layername + ".gpkg"
            LOG.info(f"saving {layer} to {filename}")
            df.to_file(filename, driver="GPKG", layer=layername)
            realization.datasets.append(
                Geopackage(
                    xml_id=layername,
                    name=layername,
                    path=filename,
                    summary=layer,
                    description=layer,
                    # get metadata/descriptions from bcdata
                    meta_data=MetaData(values=[Meta("Test", "Test Value")]),
                    layers=[
                        GeopackageLayer(
                            lyr_name=layername,
                            name=layername,
                            ds_type=GeoPackageDatasetTypes.VECTOR,
                            summary="This is a dataset",
                            description="This is a dataset",
                            citation="This is a citation",
                            meta_data=MetaData(values=[Meta("Test", "Test Value")]),
                        )
                    ],
                )
            )

    # Write xml to disk
    project.write()
    LOG.info("done")


@click.group()
def cli():
    pass


@cli.command()
@click.argument(
    "config_file", type=click.Path(exists=True), required=False, default="config.json"
)
@verbose_opt
@quiet_opt
def validate(config_file, verbose, quiet):
    """ensure sources json file is valid, and that data sources exist"""
    with open(config_file, "r") as f:
        validate_config(json.load(f))


if __name__ == "__main__":
    cli()
