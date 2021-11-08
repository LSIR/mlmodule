from typing import List, Callable, Dict, Optional, Tuple, TypeVar
import os

import numpy as np
import requests
import torch
from torch.hub import load_state_dict_from_url
import torch.nn as nn
from mlmodule.box import BBoxOutput

from mlmodule.contrib.arcface.transforms import ArcFaceAlignment
from mlmodule.torch.base import TorchMLModuleFeatures
from mlmodule.torch.data.base import MLModuleDatasetProtocol
from mlmodule.torch.data.images import transforms
from mlmodule.torch.mixins import DownloadPretrainedStateFromProvider
from mlmodule.torch.modules import Bottleneck_IR_SE, get_block
from mlmodule.torch.utils import torch_apply_state_to_partial_model, l2_norm
from mlmodule.types import ImageDatasetType


_IndexType = TypeVar('_IndexType', contravariant=True)

# Discovered by looking at OneDrive network activity when downloading a file manually from the Browser
ONE_DRIVE_API_CALL = 'https://api.onedrive.com/v1.0/drives/CEC0E1F8F0542A13/items/CEC0E1F8F0542A13!835?' \
                     'select=id,@content.downloadUrl&authkey=!AOw5TZL8cWlj10I'

# See https://quip.com/blC4A0YmfhbQ/Approach-to-remove-face-embeddings-leading-to-false-positive
ARCFACE_MEAN_DISTANCE_THRESHOLD = 0.87


class ArcFaceFeatures(TorchMLModuleFeatures[_IndexType, Tuple[ImageDatasetType, BBoxOutput]],
                      DownloadPretrainedStateFromProvider):
    """Creates face embeddings from MTCNN output"""

    state_dict_key = 'pretrained-models/face-detection/model_ir_se50.pt'

    def __init__(self, device: torch.device = None, drop_ratio: float = 0.6):
        super().__init__(device=device)
        blocks = [
            get_block(in_channel=64, depth=64, num_units=3),
            get_block(in_channel=64, depth=128, num_units=4),
            get_block(in_channel=128, depth=256, num_units=14),
            get_block(in_channel=256, depth=512, num_units=3)
        ]
        self.input_layer = nn.Sequential(
            nn.Conv2d(3, 64, (3, 3), 1, 1, bias=False),
            nn.BatchNorm2d(64),
            nn.PReLU(64))
        self.output_layer = nn.Sequential(
            nn.BatchNorm2d(512),
            nn.Dropout(drop_ratio),
            nn.Flatten(),
            nn.Linear(512 * 7 * 7, 512),
            nn.BatchNorm1d(512))
        modules = []
        for block in blocks:
            for bottleneck in block:
                modules.append(
                    Bottleneck_IR_SE(bottleneck.in_channel,
                                     bottleneck.depth,
                                     bottleneck.stride))
        self.body = nn.Sequential(*modules)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Creates the faces features"""
        x = self.input_layer(x)
        x = self.body(x)
        x = self.output_layer(x)
        return l2_norm(x)

    def get_default_pretrained_state_dict_from_provider(self) -> Dict[str, torch.Tensor]:
        """Gets the pretrained state dir from OneDrive
        URL: https://github.com/TreB1eN/InsightFace_Pytorch#2-pretrained-models--performance
        Model: IR-SE50
        """
        # Getting a download link from OneDrive
        resp = requests.get(ONE_DRIVE_API_CALL)
        resp.raise_for_status()
        download_url = resp.json()['@content.downloadUrl']

        # Downloading state dict
        pretrained_state_dict = load_state_dict_from_url(
            download_url, file_name="model_ir_se50.pth",
            map_location=self.device
        )

        # Removing deleted layers from state dict and updating the other with pretrained data
        return torch_apply_state_to_partial_model(self, pretrained_state_dict)

    def bulk_inference(
            self, data: MLModuleDatasetProtocol[_IndexType, Tuple[ImageDatasetType, BBoxOutput]],
            **options
    ) -> Optional[Tuple[List[_IndexType], np.ndarray]]:
        remove_bad_quality_faces: bool = options.pop('remove_bad_quality_faces', True)
        ret = super().bulk_inference(
            data, **options
        )
        if ret is None:
            return None
        else:
            indices, features = ret

        if remove_bad_quality_faces:
            # Getting normalised faces to filter bad quality faces
            norm_faces = np.load(os.path.join(os.path.dirname(__file__), 'normalized_faces.npy'))
            # Multiplying with a matrix that takes to mean value for each feature
            # This greatly reduces the size of the dot product with features
            norm_faces = norm_faces @ np.ones((norm_faces.shape[1], 1))/norm_faces.shape[1]

            # Filter for faces with good quality
            good_faces = (1 - (features @ norm_faces)[:, 0]) > ARCFACE_MEAN_DISTANCE_THRESHOLD
            return np.array(indices)[good_faces].tolist(), features[good_faces]
        else:
            return indices, features

    def get_dataset_transforms(self) -> List[Callable]:
        """Returns transforms to be applied on bulk_inference input data"""
        return [
            ArcFaceAlignment(),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        ]
