import os
import subprocess
from datetime import datetime
from urllib.parse import urlencode

import bcdata
import geopandas as gpd
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


def define_fwa_request(table, bounds):
    fwa_url = "https://features.hillcrestgeo.ca/fwa/collections/"
    param = {"bbox": ",".join([str(b) for b in bounds])}
    url = fwa_url + f"{table}/" + "items.json?" + urlencode(param, doseq=True)
    return url


def build_project(wsg):
    log = rsxml.Logger("Project")

    # get watershed boundary
    log.info("Downloading watershed group polygon for {wsg}")
    wsd = bcdata.get_data(
        "WHSE_BASEMAPPING.FWA_WATERSHED_GROUPS_POLY",
        query=f"WATERSHED_GROUP_CODE={wsg}",
        as_gdf=True,
        crs="EPSG:3005",
    )
    bounds = list(wsd.total_bounds)
    # bounds are required in geographic coordinates for several operations
    wsd_ll = wsd.to_crs("EPSG:4326")
    bounds_ll = list(wsd_ll.total_bounds)
    centroid_ll = (wsd_ll.centroid.x, wsd_ll.centroid.y)

    # with bbox and centroid, define project
    project = Project(
        name="Test Project",
        proj_path="project.rs.xml",
        project_type="RSContextBC",
        description="This is a test project",
        citation="This is a citation",
        bounds=ProjectBounds(
            centroid=Coords(centroid_ll[0], centroid_ll[1]),
            bounding_box=BoundingBox(
                bounds_ll[0], bounds_ll[1], bounds_ll[2], bounds_ll[3]
            ),
            filepath="project_bounds.json",
        ),
        realizations=[
            Realization(
                xml_id="test",
                name="Test Realization",
                product_version="1.0.0",
                date_created=datetime.today(),
                summary="This is a test realization",
                description="This is a test realization",
                meta_data=MetaData(values=[Meta("Test", "Test Value")]),
            )
        ],
    )
    # Now add some metadata
    project.meta_data.add_meta("Test2", "Test Value 2")

    realization = project.realizations[0]
    # get dem (automatically saved to dem.tif)
    log.info("downloading DEM")
    dem = bcdata.get_dem(bounds)

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
    log.info("generating hillshade")
    subprocess.run(
        [
            "gdaldem",
            "hillshade",
            "dem.tif",
            "hillshade.tif",
        ]
    )

    realization.datasets.append(
        Dataset(
            xml_id="hillshade",
            name="Hillshade",
            path="hillshade.tif",
            ds_type="HillShade",
            ext_ref="",
            summary="25m hillshade",
            description="25m hillshade",
        )
    )

    # create hydrology gpkg
    wsd.to_file("hydrology.gpkg", driver="GPKG", layer="watershed")

    hydrology_layers = []
    hydrology_layers.append(
        GeopackageLayer(
            lyr_name="watershed",
            name="watershed",
            ds_type=GeoPackageDatasetTypes.VECTOR,
            summary="This is a dataset",
            description="This is a dataset",
            citation="This is a citation",
            meta_data=MetaData(values=[Meta("Test", "Test Value")]),
        )
    )

    url = define_fwa_request("whse_basemapping.fwa_streams_vw", bounds_ll)
    log.debug(url)
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
            realization.datasets.append(
                Geopackage(
                    xml_id=layername,
                    name=layername,
                    path=filename,
                    summary=layer,
                    description=layer,
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

    log.info("done")


build_project(os.path.join(os.getcwd(), "project.rs.xml"))
