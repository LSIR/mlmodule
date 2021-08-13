from typing import Any, Dict, Optional, Union, List, Tuple, Generic, TypeVar

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data.dataloader import DataLoader

from mlmodule.base import BaseMLModule, LoadDumpMixin
from mlmodule.torch.data.base import IndexedDataset
from mlmodule.torch.utils import generic_inference


InputDatasetType = TypeVar('InputDatasetType', bound=IndexedDataset)


class BaseTorchMLModule(BaseMLModule, nn.Module, LoadDumpMixin, Generic[InputDatasetType]):

    default_batch_size = 128

    def __init__(self, device=None):
        super().__init__()
        self.device = device or self._resolve_device()

    @classmethod
    def _resolve_device(cls):
        return torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

    def load(self, fp=None, pretrained_getter_opts: Dict[str, Any] = None):
        """Loads model from file or from a default pretrained model if `fp=None`

        :param pretrained_getter_opts: Passed to get_default_pretrained_dict
        :param fp:
        :return:
        """

        # Getting state dict
        if fp:
            fp.seek(0)
            state = torch.load(fp)
        else:
            # Getting default pretrained state dict
            # Requires TorchPretrainedModuleMixin to be implemented
            state = self.get_default_pretrained_state_dict(**(pretrained_getter_opts or {}))

        # Loading state
        self.load_state_dict(state)
        self.to(self.device)

        return self

    def dump(self, fp):
        torch.save(self.state_dict(), fp)

    def get_data_loader(self, data, **data_loader_options):
        """Configured data loader with applied transforms

        :param data:
        :param data_loader_options:
        :return:
        """
        # Adding module transforms
        data.add_transforms(self.get_dataset_transforms())
        # Data loader default options
        data_loader_options.setdefault("shuffle", False)
        data_loader_options.setdefault("drop_last", False)
        data_loader_options["batch_size"] = data_loader_options.get("batch_size") or self.default_batch_size
        # We send to pin memory only if using CUDA device
        data_loader_options.setdefault(
            "pin_memory", self.device != torch.device('cpu'))
        # Building data loader
        return DataLoader(data, **data_loader_options)

    @classmethod
    def tensor_to_python_list_safe(cls, tensor_or_list: Union[torch.Tensor, List]) -> List:
        """Transforms a tensor into a Python list.

        If the argument is a list, returns is without raising.

        :param tensor_or_list:
        :return:
        """
        if hasattr(tensor_or_list, "tolist"):  # This is a tensor
            tensor_or_list = tensor_or_list.tolist()
        return tensor_or_list

    @classmethod
    def results_handler(cls, acc_results, new_indices, new_output: torch.Tensor):
        """

        :param acc_results: The results accumulated
        :param new_indices: The new indices of data for the current batch
        :param new_output: The new data for the current batch
        :return: new accumulated results
        """
        # Transforming new_output to Numpy
        new_output = new_output.cpu().numpy()

        # Collecting accumulated results or default value
        res_indices, res_output = acc_results or (
            [],
            np.empty((0, new_output.shape[1]), dtype=new_output.dtype)
        )

        # Adding indices
        res_indices += cls.tensor_to_python_list_safe(new_indices)

        # Adding data
        res_output = np.vstack((res_output, new_output))
        return res_indices, res_output

    def inference(self, *args, **kwargs):
        return self.__call__(*args, **kwargs)

    def bulk_inference(
            self, data: InputDatasetType,
            data_loader_options=None, result_handler_options=None, inference_options=None,
            tqdm_enabled=False
    ) -> Optional[Tuple[List, Union[List, np.ndarray]]]:    # Returns None is dataset length = 0
        """Run the model against all elements in data"""
        loader = self.get_data_loader(data, **(data_loader_options or {}))
        # Running inference batch loop
        return generic_inference(
            self, loader, self.inference, self.results_handler, self.device,
            result_handler_options=result_handler_options, inference_options=inference_options,
            tqdm_enabled=tqdm_enabled
        )

    def get_dataset_transforms(self):
        """Returns callable that transform the input data before the forward pass

        :return: List of transforms
        """
        return []
