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

	python bcbrat.py <watershed_feature_id>


## Development and testing

	$ mkdir bcbrat_env
	$ virtualenv bcbrat_env
	$ source bcbrat_env/bin/activate
	$ pip install -r requirements.txt