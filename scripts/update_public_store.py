"""This script will take model states from mlmodule.contrib and publish them to the MLModule store"""
import argparse
import dataclasses
import itertools
import logging
from typing import Iterable, List, Tuple

from mlmodule.contrib.clip.base import BaseCLIPModule
from mlmodule.contrib.clip.image import CLIPImageModule
from mlmodule.contrib.clip.parameters import PARAMETERS
from mlmodule.contrib.clip.stores import CLIPStore
from mlmodule.contrib.clip.text import CLIPTextModule
from mlmodule.contrib.resnet.modules import TorchResNetModule
from mlmodule.contrib.resnet.stores import ResNetTorchVisionStore
from mlmodule.helpers.torchvision import ResNetArch
from mlmodule.v2.base.models import ModelWithState
from mlmodule.v2.states import StateKey
from mlmodule.v2.stores.abstract import AbstractStateStore
from mlmodule.v2.stores.github import GitHUBReleaseStore

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class UpdatePublicStoreOptions:
    dry_run: bool = False


def get_mlmodule_store() -> GitHUBReleaseStore:
    return GitHUBReleaseStore("LSIR", "mlmodule")


def get_resnet_stores() -> List[Tuple[TorchResNetModule, ResNetTorchVisionStore]]:
    """ResNet models and store"""
    resnet_arch: List[ResNetArch] = [
        "resnet18",
        "resnet34",
        "resnet50",
        "resnet101",
        "resnet152",
        "resnext50_32x4d",
        "resnext101_32x8d",
        "wide_resnet50_2",
        "wide_resnet101_2",
    ]
    store = ResNetTorchVisionStore()
    ret: List[Tuple[TorchResNetModule, ResNetTorchVisionStore]] = []
    for a in resnet_arch:
        ret.append((TorchResNetModule(a), store))

    return ret


def get_clip_stores() -> List[Tuple[BaseCLIPModule, CLIPStore]]:
    """CLIP models and stores"""
    store = CLIPStore()
    ret: List[Tuple[BaseCLIPModule, CLIPStore]] = []
    for model_name in PARAMETERS:
        ret.append((CLIPImageModule(model_name), store))
        ret.append((CLIPTextModule(model_name), store))
    return ret


def get_all_models_stores() -> Iterable[Tuple[ModelWithState, AbstractStateStore]]:
    """List of all models with associated store in the contrib module"""
    return itertools.chain(get_resnet_stores(), get_clip_stores())


def iterate_state_keys_to_upload(
    mlmodule_store: AbstractStateStore,
) -> Iterable[Tuple[ModelWithState, AbstractStateStore, StateKey]]:
    """Iterates over the missing model states in MLModule store"""
    ret: List[Tuple[ModelWithState, AbstractStateStore, StateKey]] = []
    for model, provider_store in get_all_models_stores():
        # Getting available state keys in the provider store and not available in mlmodule
        state_keys = set(provider_store.get_state_keys(model.state_type)) - set(
            mlmodule_store.get_state_keys(model.state_type)
        )

        for sk in state_keys:
            ret.append((model, provider_store, sk))

    return ret


def main(options: UpdatePublicStoreOptions):
    mlmodule_store = get_mlmodule_store()
    for item in iterate_state_keys_to_upload(mlmodule_store):
        model, provider_store, state_key = item
        logger.info(f"Saving {state_key} to MLModule store")
        if not options.dry_run:
            provider_store.load(model, state_key)
            mlmodule_store.save(model, training_id=state_key.training_id)


def parse_arguments() -> UpdatePublicStoreOptions:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run, does not execute anything."
    )

    return UpdatePublicStoreOptions(**vars(parser.parse_args()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(parse_arguments())
