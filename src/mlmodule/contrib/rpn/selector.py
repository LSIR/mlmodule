import logging
from typing import Any, List, Tuple, TypeVar
import numpy as np

import torch
from torch.utils.data.dataloader import DataLoader
from tqdm import tqdm

from mlmodule.base import BaseMLModule
from mlmodule.box import BBoxOutput, BBoxCollection
from mlmodule.torch.data.base import IndexedDataset


logger = logging.getLogger(__name__)

""" Given regions extracted from images, filters some of them out to reduce redundancy """


InputDatasetType = TypeVar('InputDatasetType', bound=IndexedDataset[Any, Any, BBoxCollection])


class CosineSimilarityRegionSelector(BaseMLModule):
    """ Filters regions based on the cosine similarity between their encodings. """

    def __init__(self, device=None):
        super().__init__()
        self.device = device or self._resolve_device()

    @classmethod
    def _resolve_device(cls):
        return torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

    @classmethod
    def similarity(cls, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return np.dot(x/x.sum(), y/y.sum())

    def get_data_loader(self, data):
        """Configured data loader with applied transforms

        :param data:
        :param data_loader_options:
        :return:
        """
        # Data loader options options
        data_loader_options = {
            "shuffle": False,
            "drop_last": False,
            "batch_size": 1,
            "pin_memory": self.device != torch.device('cpu'),
            "collate_fn": lambda x: ([x[0][0]], x[0][1])
        }
        # Building data loader
        return DataLoader(data, **data_loader_options)

    def bulk_inference(
            self, data: InputDatasetType, max_similarity=0.75, tqdm_enabled=False
    ) -> Tuple[list, List[BBoxCollection]]:
        indices: List[Any] = []
        bbox_collections: List[BBoxCollection] = []
        data_loader = self.get_data_loader(data)

        with torch.no_grad():
            n_batches = len(data_loader)
            if tqdm_enabled:
                data_loader = tqdm(data_loader)
            for batch_n, (img_index, img_boxes) in enumerate(data_loader):
                logger.debug(f"Sending batch number: {batch_n}/{n_batches}")

                # img_index: List containing one index
                # img_boxes: BBoxCollection
                # Collect the features for each box
                box_features = [box.features for box in img_boxes]

                for i1 in range(len(box_features) - 1):
                    # if the box is still valid, compute the cosine
                    if box_features[i1] is not None:
                        for i2 in range(i1 + 1, len(box_features)):
                            similarity = self.similarity(box_features[i1], box_features[i2])
                            # if the 2 boxes are too similar, set the features for the worst box to None
                            if similarity > max_similarity:
                                box_features[i2] = None

                # Reconstruct the BBoxCollection
                new_img_boxes = []
                for i, box in enumerate(img_boxes):
                    new_img_boxes.append(
                        BBoxOutput(
                            bounding_box=(box.bounding_box[0], box.bounding_box[1]),
                            probability=box.probability,
                            features=box_features[i],
                        )
                    )

                indices.append(img_index[0])
                bbox_collections.append(new_img_boxes)

                logger.debug(f"Collecting results: {batch_n}/{n_batches}")

            # Returning accumulated results
        return indices, bbox_collections
