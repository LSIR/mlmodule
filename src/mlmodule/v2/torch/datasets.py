import dataclasses
from typing import BinaryIO, Callable, Generic, List, Optional, Sequence, Tuple, TypeVar

import PIL.Image
from PIL.Image import Image
from typing_extensions import Protocol

_IndicesType = TypeVar("_IndicesType", covariant=True)
_DatasetType = TypeVar("_DatasetType", covariant=True)
_NewDatasetType = TypeVar("_NewDatasetType", covariant=True)


class TorchDataset(Protocol[_IndicesType, _DatasetType]):
    """PyTorch dataset protocol

    In order to be used with the PyTorch runners, a TorchDataset
    should expose two functions `__getitem__` and `__len__`.
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

    def __getitem__(self, index: int) -> Tuple[_IndicesType, _NewDatasetType]:
        ret_index, data = self.dataset.__getitem__(index)
        return ret_index, self.transform_func(data)

    def __len__(self) -> int:
        return self.dataset.__len__()


@dataclasses.dataclass
class ListDataset(TorchDataset[int, _DatasetType]):
    """Simple dataset that contains a list of objects in memory

    Attributes:
        objects (List[Any]): List of objects of the dataset
    """

    objects: Sequence[_DatasetType]

    def __getitem__(self, index: int) -> Tuple[int, _DatasetType]:
        return index, self.objects[index]

    def __len__(self) -> int:
        return len(self.objects)


@dataclasses.dataclass
class ListDatasetIndexed(TorchDataset[_IndicesType, _DatasetType]):
    """Simple dataset that contains a list of objects in memory

    Attributes:
        objects (List[Any]): List of objects of the dataset
    """

    indices: Sequence[_IndicesType]
    objects: Sequence[_DatasetType]

    def __getitem__(self, index: int) -> Tuple[_IndicesType, _DatasetType]:
        return self.indices[index], self.objects[index]

    def __len__(self) -> int:
        return len(self.objects)


@dataclasses.dataclass
class OpenBinaryFileDataset(TorchDataset[str, BinaryIO]):
    """Dataset that returns `typing.BinaryIO` from a list of local file names

    Attributes:
        paths (List[str]): List of paths to files
    """

    paths: List[str]

    def __getitem__(self, index: int) -> Tuple[str, BinaryIO]:
        return self.paths[index], open(self.paths[index], mode="rb")

    def __len__(self) -> int:
        return len(self.paths)


@dataclasses.dataclass
class OpenImageFileDataset(TorchDataset[str, Image]):
    """Dataset that returns `PIL.Image.Image` from a list of local file names

    Attributes:
        paths (List[str]): List of paths to image files
        resize_image_size (tuple[int, int] | None): Optionally reduce the image size on load
    """

    paths: List[str]
    resize_image_size: Optional[Tuple[int, int]] = None

    def _open_image(self, path: str) -> Image:
        image = PIL.Image.open(path)
        if self.resize_image_size:
            # For shrink on load
            # See https://stackoverflow.com/questions/57663734/how-to-speed-up-image-loading-in-pillow-python
            image.draft(None, self.resize_image_size)
            return image.resize(self.resize_image_size)
        return image

    def __getitem__(self, index: int) -> Tuple[str, Image]:
        return self.paths[index], self._open_image(self.paths[index])

    def __len__(self) -> int:
        return len(self.paths)
