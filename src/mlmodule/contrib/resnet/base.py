from typing import TypeVar

import torchvision.models as m
from torch.hub import load_state_dict_from_url

from mlmodule.torch.base import TorchMLModuleFeatures
from mlmodule.torch.utils import torch_apply_state_to_partial_model
from mlmodule.types import ImageDatasetType

_IndexType = TypeVar("_IndexType")


class BaseResNetImageNetModule(TorchMLModuleFeatures[_IndexType, ImageDatasetType]):
    def __init__(self, resnet_arch, device=None):
        super().__init__(device=device)
        self.resnet_arch = resnet_arch

    @classmethod
    def get_resnet_module(cls, resnet_arch):
        # Getting the ResNet architecture https://pytorch.org/docs/stable/torchvision/models.html
        return getattr(m, resnet_arch)()

    def get_default_pretrained_state_dict(self, **_opts):
        """Returns the state dict for a pretrained resnet model
        :return:
        """
        # Getting URL to download model
        url = m.resnet.model_urls[self.resnet_arch]
        # Downloading state dictionary
        pretrained_state_dict = load_state_dict_from_url(url)
        # Removing deleted layers from state dict and updating the other with pretrained data
        return torch_apply_state_to_partial_model(self, pretrained_state_dict)
