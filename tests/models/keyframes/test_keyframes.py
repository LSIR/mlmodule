from io import BytesIO

import pytest
import torch

from mlmodule.callbacks.memory import CollectVideoFramesInMemory
from mlmodule.models.keyframes.datasets import (
    FPSVideoFrameExtractorTransform,
    compute_every_param_from_target_fps,
)
from mlmodule.models.keyframes.encoders import VideoFramesEncoder
from mlmodule.models.keyframes.pretrained import torch_keyframes_resnet_imagenet
from mlmodule.models.resnet.modules import TorchResNetModule
from mlmodule.torch.datasets import ListDataset
from mlmodule.torch.options import TorchRunnerOptions
from mlmodule.torch.runners import TorchInferenceRunner


@pytest.mark.parametrize(
    ("video_fps", "max_target_fps", "result"),
    [
        (24.0, 1, 24),
        (24.0, 12, 2),
        (24.0, 48, 1),
        (11.0, 2, 6),
    ],
)
def test_compute_every_param_from_target_fps(
    video_fps: float, max_target_fps: int, result: int
):
    assert compute_every_param_from_target_fps(video_fps, max_target_fps) == result


def test_fps_video_extractor(video_file_path: str):
    with open(video_file_path, mode="rb") as video_file:
        frames = FPSVideoFrameExtractorTransform(fps=1)(video_file)
    assert len(frames) == 2
    assert len(frames[0]) == 83
    assert len(frames[1]) == 83


@pytest.mark.parametrize(
    ("fps", "expected_n_frames"), [(1, 83), (0.001, 1)], ids=["1fps", "1/1000fps"]
)
def test_video_frame_encoder(
    video_file_path: str, torch_device: torch.device, fps: float, expected_n_frames: int
):
    with open(video_file_path, mode="rb") as video_file:
        dataset = ListDataset([video_file])

        model = VideoFramesEncoder(
            image_encoder=TorchResNetModule("resnet18"), device=torch_device, fps=fps
        )
        features = CollectVideoFramesInMemory()
        runner = TorchInferenceRunner(
            model=model,
            dataset=dataset,
            callbacks=[features],
            options=TorchRunnerOptions(
                device=torch_device, data_loader_options={"batch_size": 1}
            ),
        )
        runner.run()

    assert features.frames[0].features is not None
    assert len(features.frames[0].features) == expected_n_frames


def test_keyframes_extractor(torch_device: torch.device, video_file_path: str):
    with open(video_file_path, mode="rb") as video_file:
        dataset = ListDataset([video_file])

        model = torch_keyframes_resnet_imagenet("resnet18", device=torch_device)
        features = CollectVideoFramesInMemory()
        runner = TorchInferenceRunner(
            model=model,
            dataset=dataset,
            callbacks=[features],
            options=TorchRunnerOptions(device=torch_device),
        )
        runner.run()

    assert len(features.indices) == 1
    assert len(features.frames) == 1
    assert features.frames[0].features is not None
    assert len(features.frames[0].features) > 0
    assert len(features.frames[0].features) < 21


def test_keyframes_extractor_bad_file(torch_device: torch.device):
    dataset = ListDataset([BytesIO(b"bbbbbb")])

    model = torch_keyframes_resnet_imagenet("resnet18", device=torch_device)
    features = CollectVideoFramesInMemory()
    runner = TorchInferenceRunner(
        model=model,
        dataset=dataset,
        callbacks=[features],
        options=TorchRunnerOptions(device=torch_device),
    )
    runner.run()

    assert len(features.indices) == 1
    assert len(features.frames) == 1
    assert features.frames[0].features is not None
    assert len(features.frames[0].features) == 0
