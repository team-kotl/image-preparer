# Image Preparation Scripts

This repository contains the scripts to download the Sentinel-2 Imagery to be used as raw data for the TerraMap model.

### Create your conda environment

```shell
conda create -n ee
conda activate ee
conda install --file requirements.txt -c conda-forge
```

### Authenticate to Google Earth Engine

```python
# Run your interactive python terminal [python] and execute each line
import ee
ee.Authenticate()
exit()
```