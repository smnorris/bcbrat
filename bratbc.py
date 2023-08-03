# try and generate a very simple BRAT project
import subprocess

import bcdata
import requests
import rsxml


# get watershed boundary
wsd = bcdata.get_data(
    "WHSE_BASEMAPPING.FWA_ASSESSMENT_WATERSHEDS_POLY",
    query="WATERSHED_FEATURE_ID=2904",
    as_gdf=True,
    crs="EPSG:3005",
)

# get dem (automatically saved to dem.tif)
dem = bcdata.get_dem(list(wsd.total_bounds))

# generate simple hillshade with gdaldem
subprocess.run(
    [
        "gdaldem",
        "hillshade",
        "dem.tif",
        "hillshade.tif",
    ]
)

# download hydrology



# download veg/roads/rail/bec/other
