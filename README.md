# BC BRAT

Experimental tool for generating BRAT project data for British Columbia watersheds.

	
## Dependencies

#### Software

`gdal`/`geopandas`/`rasterio` are required - install these to your system first. 

When complete, install the final Python dependencies with `pip`:

	pip install -r requirements.txt


#### Services

Data are downloaded from:

- DataBC WFS (via `bcdata`)
- [features.hillcrestgeo.ca](https://features.hillcrestgeo.ca/fwa/index.html) (value added streams)


## Usage

	python bcbrat.py --help


Create a BRAT data package and xml project file with minimal/default data, writing/overwriting folder `brat_<watershed_group_code>`:

	python bcbrat.py <watershed_group_code> 

Create a BRAT data package and xml project file with minimal/default data, writing outputs to `my_brat_project`

	python bcbrat.py <watershed_group_code> -o my_brat_project

Create a BRAT data package and xml project file with additional data as defined by `brat.conf`:

	python bcbrat.py <watershed_group_code> -c brat.conf


## Development and testing

	$ mkdir bcbrat_env
	$ virtualenv bcbrat_env
	$ source bcbrat_env/bin/activate
	$ pip install -r requirements.txt
	$ py.test