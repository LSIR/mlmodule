# MLModule developer guide

## Installation

### Using `tox`

This method requires [`conda`](https://docs.conda.io/en/latest/) and [`tox`](https://tox.readthedocs.io/en/latest/) to be installed.

Create a development environment:

```shell
# CPU development
tox --devenv venv -e py37
# or CUDA 11.0
tox --devenv venv -e cuda110-py37
# or CUDA 11.0 on PC32 (compute ability 3.5)
tox --devenv venv -e cuda110-ca35-py37
```

The environment can be activated with:

```shell
conda activate ./venv
```

### Using `pip`

This method requires `pip` to be installed

```bash
pip install -r requirements.txt
# To install MLModule in development mode with all dependencies
pip install -e .
```

## Testing

Testing can be done using `tox`

```shell
# CPU testing
tox -e py37
# or CUDA 11.0
tox -e cuda110-py37
# or CUDA 11.0 on PC32
tox -e cuda110-ca35-py37
```

or with directly using `pytest` on an environment with all dependencies installed

```shell
pytest
```

## Packaging

MLModules is distributed via wheels on the 
[LSIR public assets](https://github.com/LSIR/dataplatform-infra/tree/main/lsir-public-assets) 
bucket.

A wheel can be created with the [`build`](https://pypi.org/project/build/) module

```shell
MLMODULE_BUILD_VERSION=x.y.z python -m build --wheel
```

## Requirements

Updating requirements should be done in `setup.cfg`. 
To update the `requirement.txt` file run:

```bash
pip-compile --extra full --upgrade
```

## Publish a new version

* Push the new version to the `master` branch
* Add a tag on the branch with the format `vX.Y.Z`. For instance, `v0.1.1`.
* Follow the guide in 
  [dataplatform-infra/build-ml-module](https://github.com/LSIR/dataplatform-infra/tree/main/build-ml-module)
  to build and upload the new release
