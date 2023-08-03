# BC BRAT

Experimental tool for generating BRAT project data for British Columbia watersheds.

	
## Dependencies

#### Software

`gdal`/`geopandas`/`rasterio` are required - install these to your system (consider using conda), then install the final Python dependencies:

`pip install requirements.txt`

#### Services

Data are downloaded from:

- DataBC WFS (via `bcdata`)
- [features.hillcrestgeo.ca](https://features.hillcrestgeo.ca/fwa/index.html) (value added streams)


## Usage

	python bcbrat.py <watershed_feature_id>



