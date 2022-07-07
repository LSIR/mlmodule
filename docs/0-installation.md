# Installation

We support `Python >= {{develop.python_version}}` and `PyTorch >= {{develop.pytorch_version}}`.
However, it is likely that MoZuMa can be run on previous versions of PyTorch, we are simply not testing it
for versions before `{{develop.pytorch_version}}`.

## Pre-requisites

First, you need to install PyTorch and TorchVision.
See the official
[PyTorch's documentation](https://pytorch.org/get-started/locally/#start-locally)
for installation instructions.
We recommend using the [`conda`](https://docs.conda.io/en/latest/) package manager to install PyTorch.

## Installing with `pip`

Once PyTorch and TorchVision are installed,
MoZuMa can be directly installed from the git repository
using `pip`.

```bash
# To install the latest developments
pip install git+https://github.com/mozuma/mozuma
# Or to install a specific version X.Y.Z
pip install git+https://github.com/mozuma/mozuma@vX.Y.Z
```

## Using Docker

For convenience, we also ship a base [Docker image](https://hub.docker.com/repository/docker/lsirepfl/mlmodulekit)
which contains dependencies that can be hard to install (for instance PyTorch).

See [MLModuleKit](3-mlmodulekit.md) for usage documentation.
