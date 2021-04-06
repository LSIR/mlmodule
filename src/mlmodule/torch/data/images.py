from pathlib import Path
from typing import List, TypeVar, Union, IO

import numpy as np
from PIL import Image
from torchvision import transforms

from mlmodule.torch.data.base import IndexedDataset
from mlmodule.torch.data.files import ReadablePathType

TORCHVISION_STANDARD_IMAGE_TRANSFORMS = [
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
]


def get_pil_image_from_file(file: Union[str, Path, IO]) -> Image.Image:
    """PIL read image from a file"""
    return Image.open(file)


def convert_to_rgb(pil_image: Image.Image) -> Image.Image:
    """PIL convert to RGB function"""
    return pil_image.convert('RGB')


IndicesType = TypeVar('IndicesType')


class BaseImageDataset(IndexedDataset[IndicesType, ReadablePathType, Union[Image.Image, np.ndarray]]):
    """Dataset returning a tuple with an index and an image"""

    def __init__(self, indices: List[IndicesType], image_path: List[str], to_rgb=True):
        super().__init__(indices, image_path)
        self.add_transforms([get_pil_image_from_file])
        if to_rgb:
            self.add_transforms([convert_to_rgb])


class ImageDataset(BaseImageDataset[str]):
    """Same as base Image dataset but working with references to local paths"""

    def __init__(self, image_path: List[str], to_rgb=True):
        super().__init__(image_path, image_path, to_rgb=to_rgb)
