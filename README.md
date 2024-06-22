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

Create/edit a config file as required, using `config.json` as a guide.
The key item to change is how the watershed is defined, via the keys `watershed_source` and `watershed_query`. Any data source available through `bcdata` can be used.

Once your config file is ready with the appropriate watershed query, validate the config and the query:


	python bcbrat.py --validate

If the file validates successfully, run the job:

	python bcbrat.py 

This will download required data and create a riverscapes project .xml file - all data will be written to a new folder derived from the `project_name` key in the config. Optionally, write to a specified folder:

	python bcbrat.py -o my_project

Or specify a config file other than the default:

	python bcbrat.py my_config.json -o my_project

## Development and testing

	$ mkdir bcbrat_env
	$ virtualenv bcbrat_env
	$ source bcbrat_env/bin/activate
	$ pip install -r requirements.txt
	$ py.test