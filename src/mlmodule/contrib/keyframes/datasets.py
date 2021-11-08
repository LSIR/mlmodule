import dataclasses
import math
import shutil
import tempfile
from typing import IO, BinaryIO, Generic, Iterator, List, Tuple, TypeVar

import cv2
import numpy as np
from PIL.Image import Image

from mlmodule.types import FrameIdxType, FrameSequenceType
from mlmodule.utils import convert_cv2_image_to_pil


_IndexType = TypeVar("_IndexType")


def extract_video_frames(
    video_stream: cv2.VideoCapture, every_n_frames: int
) -> Iterator[Tuple[FrameIdxType, Image]]:
    """Generator of video frames extracted from a video

    Args:
        video_stream: Video capture from cv2
        every_n_frames: If set to 24 on a 24FPS video, it will extract 1 frame / sec
    """
    frame_idx: int = 0
    grabbed: bool
    frame: np.ndarray
    while True:
        grabbed, frame = video_stream.read()
        if not grabbed:
            # We reached the end of the video
            break

        if frame_idx % every_n_frames == 0:
            # Return the current frame
            yield frame_idx, convert_cv2_image_to_pil(frame)

        frame_idx += 1


@dataclasses.dataclass
class BinaryVideoCatpure:
    """Adds support for cv2.VideoCapture to read from binary data

    It uses a local temporary file to pass a valid path to the cv2.VideoCapture class
    """

    video_bin: BinaryIO

    _video_capture: cv2.VideoCapture = dataclasses.field(init=False)
    _tmp_video_file: IO[bytes] = dataclasses.field(init=False)

    def __enter__(self) -> cv2.VideoCapture:
        self._tmp_video_file = tempfile.NamedTemporaryFile()
        shutil.copyfileobj(self.video_bin, self._tmp_video_file)
        self._video_capture = cv2.VideoCapture(self._tmp_video_file.name)
        return self._video_capture

    def __exit__(self, type, value, traceback) -> None:
        self._video_capture.release()
        self._tmp_video_file.close()


def compute_every_param_from_target_fps(video_fps: float, max_target_fps: int) -> int:
    """Computes the every_n_frame parameter of the function extract_video_frames

    It returns the frames to keep to obtain an output of max_target_fps form a video of video_fps.

    For instance:
        max_target_fps=1, video_fps=24 -> returns 24
        max_target_fps=12, video_fps=24 -> returns 2
        max_target_fps=24, video_fps=24 -> returns 1
        max_target_fps=48, video_fps=24 -> returns 1
    """
    return max(math.ceil(video_fps / max_target_fps), 1)


@dataclasses.dataclass
class FPSVideoFrameExtractor(Generic[_IndexType]):
    indices: List[_IndexType]
    video_files: List[BinaryIO]
    fps: int
    # Number of frames per second to return

    def __getitem__(self, index: int) -> Tuple[_IndexType, FrameSequenceType]:
        with BinaryVideoCatpure(self.video_files[index]) as capture:
            every_n_frames = compute_every_param_from_target_fps(
                capture.get(cv2.CAP_PROP_FPS), self.fps
            )
            frame_indices: List[int] = []
            frame_images: List[Image] = []
            for frame_idx, frame_img in extract_video_frames(capture, every_n_frames=every_n_frames):
                frame_indices.append(frame_idx)
                frame_images.append(frame_img)
            return self.indices[index], (frame_indices, frame_images)

    def __len__(self) -> int:
        return len(self.video_files)