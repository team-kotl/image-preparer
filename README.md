# Image Preparation Scripts

This repository contains the scripts to download the Sentinel-2 Imagery to be used as raw data for the TerraMap model.

### Create your conda environment

```shell
conda create --prefix ./ee # You can select this as your interpreter in VS Code to automate activation
conda activate ./ee 
conda install --file requirements.txt -c conda-forge
```

### Authenticate to Google Earth Engine

```python
# Run your interactive python terminal [python] and execute each line
import ee
ee.Authenticate()
exit()
```

### Order of script execution

> Before executing each script, please ensure that you update the YEAR constant beforehand.

1. get-imagery.py
2. combine-tiles.py
3. clip.py