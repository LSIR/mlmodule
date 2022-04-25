import dataclasses
import pathlib
from typing import (
    BinaryIO,
    Callable,
    Generic,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

import numpy as np
import PIL.Image
from PIL.Image import Image
from typing_extensions import Protocol

from mlmodule.v2.base.predictions import BatchBoundingBoxesPrediction
from mlmodule.v2.torch.utils import apply_mode_to_image

_IndicesType = TypeVar("_IndicesType", covariant=True)
_DatasetType = TypeVar("_DatasetType", covariant=True)
_NewDatasetType = TypeVar("_NewDatasetType", covariant=True)
_PathLike = TypeVar("_PathLike", bound=Union[str, pathlib.Path])
_TargetsType = TypeVar("_TargetsType", covariant=True)


class TorchDataset(Protocol[_IndicesType, _DatasetType]):
    """PyTorch dataset protocol

    In order to be used with the PyTorch runners, a TorchDataset
    should expose two functions `__getitem__` and `__len__`.
    """

    def getitem_indices(self, index: int) -> _IndicesType:
        """The value of dataset indices at index position

        Arguments:
            index (int): The position of the element to get
        Returns:
            _IndicesType: The value of the indices at the position
        """

    def __getitem__(self, index: int) -> Tuple[_IndicesType, _DatasetType]:
        """Get an item of the dataset by index

        Arguments:
            index (int): The index of the element to get
        Returns:
            Tuple[_IndicesType, _DatasetType]: A tuple of dataset index of the element
                and value of the element
        """
        ...

    def __len__(self) -> int:
        """Length of the dataset

        Returns:
            int: The length of the dataset
        """
        ...


@dataclasses.dataclass
class TorchDatasetTransformsWrapper(
    TorchDataset[_IndicesType, _NewDatasetType],
    Generic[_IndicesType, _DatasetType, _NewDatasetType],
):
    """Wraps a dataset with transforms

    The returned object is a TorchDataset that can be used in DataLoader
    """

    # The source dataset
    dataset: TorchDataset[_IndicesType, _DatasetType]
    # The transform function
    transform_func: Callable[[_DatasetType], _NewDatasetType]

    def getitem_indices(self, index: int) -> _IndicesType:
        return self.dataset.getitem_indices(index)

    def __getitem__(self, index: int) -> Tuple[_IndicesType, _NewDatasetType]:
        ret_index, data = self.dataset.__getitem__(index)
        return ret_index, self.transform_func(data)

    def __len__(self) -> int:
        return self.dataset.__len__()


@dataclasses.dataclass
class ListDataset(TorchDataset[int, _DatasetType]):
    """Simple dataset that contains a list of objects in memory

    Attributes:
        objects (Sequence[_DatasetType]): List of objects of the dataset
    """

    objects: Sequence[_DatasetType]

    def getitem_indices(self, index: int) -> int:
        return index

    def __getitem__(self, index: int) -> Tuple[int, _DatasetType]:
        return index, self.objects[index]

    def __len__(self) -> int:
        return len(self.objects)


@dataclasses.dataclass
class ListDatasetIndexed(TorchDataset[_IndicesType, _DatasetType]):
    """Simple dataset that contains a list of objects in memory with custom indices

    Attributes:
        indices (Sequence[_IndicesType]): Indices to track objects in results
        objects (Sequence[_DatasetType]): List of objects of the dataset
    """

    indices: Sequence[_IndicesType]
    objects: Sequence[_DatasetType]

    def getitem_indices(self, index: int) -> _IndicesType:
        return self.indices[index]

    def __getitem__(self, index: int) -> Tuple[_IndicesType, _DatasetType]:
        return self.indices[index], self.objects[index]

    def __len__(self) -> int:
        return len(self.objects)


@dataclasses.dataclass
class LocalBinaryFilesDataset(TorchDataset[_PathLike, BinaryIO]):
    """Dataset that reads a list of local file names and returns their content as bytes

    Attributes:
        paths (Sequence[_PathLike]): List of paths to files
    """

    paths: Sequence[_PathLike]

    def getitem_indices(self, index: int) -> _PathLike:
        return self.paths[index]

    def __getitem__(self, index: int) -> Tuple[_PathLike, BinaryIO]:
        return self.paths[index], open(self.paths[index], mode="rb")

    def __len__(self) -> int:
        return len(self.paths)


@dataclasses.dataclass
class ImageDataset(TorchDataset[_IndicesType, Image]):
    """Dataset that returns `PIL.Image.Image` from a dataset of images in bytes format

    Attributes:
        binary_files_dataset (TorchDataset[_IndicesType, bytes]): Dataset to load images.
            Usually a [`LocalBinaryFilesDataset`][mlmodule.v2.torch.datasets.LocalBinaryFilesDataset].
        resize_image_size (tuple[int, int] | None): Optionally reduce the image size on load
        mode (str | None): Optional mode to apply when loading the image. See PIL `Image.draft` parameters.
    """

    binary_files_dataset: TorchDataset[_IndicesType, BinaryIO]
    resize_image_size: Optional[Tuple[int, int]] = None
    mode: Optional[str] = "RGB"

    def getitem_indices(self, index: int) -> _IndicesType:
        return self.binary_files_dataset.getitem_indices(index)

    def transform_image_on_load(self, image: Image) -> Image:
        if self.resize_image_size is None and self.mode is None:
            return image

        # For shrink on load
        # See https://stackoverflow.com/questions/57663734/how-to-speed-up-image-loading-in-pillow-python
        image.draft(mode=self.mode, size=self.resize_image_size)

        # Applying transforms to ensure we have the right size and mode
        if self.resize_image_size:
            image = image.resize(self.resize_image_size)
        if self.mode:
            image = apply_mode_to_image(image, self.mode)

        return image

    def _open_image(self, bin_image: BinaryIO) -> Image:
        with bin_image:
            image = PIL.Image.open(bin_image)
            # Optionally transform and load the image
            image = self.transform_image_on_load(image)
            # Loading image in-memory to allow close bin_image
            image.load()
            return image

    def __getitem__(self, index: int) -> Tuple[_IndicesType, Image]:
        image_index, bin_image = self.binary_files_dataset[index]
        return image_index, self._open_image(bin_image)

    def __len__(self) -> int:
        return len(self.binary_files_dataset)


@dataclasses.dataclass
class ImageBoundingBoxDataset(
    TorchDataset[
        Tuple[_IndicesType, int], Tuple[Image, BatchBoundingBoxesPrediction[np.ndarray]]
    ]
):
    """Dataset that returns tuple of `Image` and bounding box data from a list of file names and bounding box information

    Attributes:
        image_dataset (TorchDataset[_IndicesType, Image]): The dataset of images
        bounding_boxes (Sequence[BatchBoundingBoxesPrediction[np.ndarray]]):
            The bounding boxes predictions for all given images
        crop_image (bool): Whether to crop the image at the bounding box when loading it
    """

    image_dataset: TorchDataset[_IndicesType, Image]
    bounding_boxes: Sequence[BatchBoundingBoxesPrediction[np.ndarray]]
    crop_image: bool = False

    def __post_init__(self):
        # Flatten all bounding box for all images
        self.flat_indices: List[Tuple[int, _IndicesType, int]] = [
            (
                image_position,
                self.image_dataset.getitem_indices(image_position),
                box_index,
            )
            for image_position, boxes in enumerate(self.bounding_boxes)
            for box_index in range(len(boxes.bounding_boxes))
        ]

    def getitem_indices(self, index: int) -> Tuple[_IndicesType, int]:
        return self.flat_indices[index][1:]

    def get_image(self, image_position: int, box_index: int) -> Image:
        image = self.image_dataset[image_position][1]
        if not self.crop_image:
            return image

        return image.crop(self.bounding_boxes[image_position].bounding_boxes[box_index])

    def __getitem__(
        self, index: int
    ) -> Tuple[
        Tuple[_IndicesType, int], Tuple[Image, BatchBoundingBoxesPrediction[np.ndarray]]
    ]:
        # Getting the image position (int), image index and bounding box index
        image_position, image_index, box_index = self.flat_indices[index]

        return (image_index, box_index), (
            # Image data
            self.get_image(image_position, box_index),
            # Bounding box data
            self.bounding_boxes[image_position].get_by_index(box_index),
        )

    def __len__(self) -> int:
        return len(self.flat_indices)


class TorchTrainingDataset(Protocol[_DatasetType, _TargetsType]):
    """PyTorch dataset protocol for protocol

    In order to be used with the PyTorch training runners, a TorchTrainingDataset
    should expose the function `__getitem__`.
    """

    def __getitem__(self, index: int) -> Tuple[_DatasetType, _TargetsType]:
        """Get an item of the dataset by index with its target class

        Arguments:
            index (int): The index of the element to get
        Returns:
            Tuple[_IndicesType, _TargetType]: A tuple of dataset element
                and the class_index of the target class.
        """
        ...


@dataclasses.dataclass
class TorchTrainingDatasetTransformsWrapper(
    TorchDatasetTransformsWrapper, TorchTrainingDataset[_NewDatasetType, _TargetsType]
):
    """Similar to TorchDatasetTransformsWrapper but can be used
    with training datasets
    """

    def __getitem__(self, index: int) -> Tuple[_NewDatasetType, _TargetsType]:
        data, target = self.dataset.__getitem__(index)
        return self.transform_func(data), target


@dataclasses.dataclass
class LocalBinaryFilesTrainingDataset(
    LocalBinaryFilesDataset, TorchTrainingDataset[BinaryIO, int]
):
    """Training dataset that reads a list of local file names
    and returns their content as bytes

    Attributes:
        paths (Sequence[str]): List of paths to files
        labels (Sequence[str]): List of classes, one for each element in `path`
    """

    labels: Sequence[str]
    classes: Sequence[str] = dataclasses.field(init=False, default_factory=set)
    classes_to_idx: dict = dataclasses.field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.paths) != len(self.labels):
            raise ValueError("Length for classes doensn't match lenght for labels")

        self._make_classes()

    def _make_classes(self) -> None:
        for label in self.labels:
            if label not in self.classes:
                self.classes.add(label)
                self.classes_to_idx[label] = len(self.classes) - 1

    def __getitem__(self, index: int) -> Tuple[BinaryIO, int]:
        _, file = super().__getitem__(index)

        return (
            file,
            self.classes_to_idx[self.labels[index]],
        )


@dataclasses.dataclass
class ImageTrainingDataset(ImageDataset, TorchTrainingDataset[Image, int]):
    """Trainig dataset that returns `PIL.Image.Image` from a dataset of images in bytes format

    Attributes:
        binary_files_dataset (TorchDataset[Image, int]): Training dataset to load images.
            Usually a [`LocalBinaryFilesTrainingDataset`][mlmodule.v2.torch.datasets.LocalBinaryFilesTrainingDataset].
        resize_image_size (tuple[int, int] | None): Optionally reduce the image size on load
        mode (str | None): Optional mode to apply when loading the image. See PIL `Image.draft` parameters.
    """

    binary_files_dataset: TorchTrainingDataset[Image, int]

    def __getitem__(self, index: int) -> Tuple[Image, int]:
        bin_image, target = self.binary_files_dataset[index]
        return (self._open_image(bin_image), target)
