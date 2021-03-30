import pytest
import torch
from _pytest.fixtures import SubRequest

from mlmodule.contrib.clip import CLIPViTB32ImageEncoder
from mlmodule.contrib.densenet import DenseNet161ImageNetFeatures, DenseNet161ImageNetClassifier, \
    DenseNet161PlacesFeatures, DenseNet161PlacesClassifier
from mlmodule.contrib.resnet import ResNet18ImageNetFeatures, ResNet18ImageNetClassifier


@pytest.fixture(params=["cpu", "cuda"])
def torch_device(request: SubRequest):
    """Fixture for the PyTorch device, run GPU only when CUDA is available

    :param request:
    :return:
    """
    if request.param != 'cpu' and not torch.cuda.is_available():
        pytest.skip(f"Skipping device {request.param}, CUDA not available")
    return torch.device(request.param)


@pytest.fixture(params=[
    ResNet18ImageNetFeatures,
    ResNet18ImageNetClassifier,
    DenseNet161ImageNetFeatures,
    DenseNet161ImageNetClassifier,
    DenseNet161PlacesFeatures,
    DenseNet161PlacesClassifier,
    CLIPViTB32ImageEncoder
])
def data_platform_scanner(request: SubRequest):
    """Fixture for generic tests of Modules to be used in the data platform

    :param request:
    :return:
    """
    return request.param
