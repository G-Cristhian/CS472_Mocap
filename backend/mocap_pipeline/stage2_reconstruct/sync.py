"""
Stage 2a: put every camera on one clock using the clap.

Input : the video paths and their Keypoints2D.
Output: SyncResult, plus Keypoints2D resampled onto the shared timeline.
"""
from __future__ import annotations

from ..schemas import Keypoints2D, SyncResult


def find_clap_time(video_path: str) -> float:
    """
    Seconds into this video at which the clap occurs.

    TODO:
      1. Extract the audio track (ffmpeg to mono wav, or a library).
      2. Look only at the first config.CLAP_SEARCH_WINDOW_S seconds.
      3. The clap is the sharpest loud transient: find the peak of the
         short-time energy (or the largest jump in amplitude).
      4. Raise a clear error if no obvious peak exists, so the user knows to
         re-record instead of getting silently wrong 3D.
    Refinement for later: cross-correlate each camera's audio against
    camera 0's around the clap for sub-frame accuracy.
    """
    raise NotImplementedError


def synchronise(video_paths: list[str],
                keypoints: list[Keypoints2D]) -> tuple[SyncResult, list[Keypoints2D]]:
    """
    TODO:
      1. find_clap_time for each video.
      2. Shift each camera's timestamps so the clap is t = 0.
      3. Shared timeline: from 0 to the earliest end time among cameras, at
         config.TARGET_FPS.
      4. Resample every camera's points and confidence onto that timeline by
         linear interpolation between its two nearest frames. If either
         neighbour is NaN the result is NaN.
      5. Return the SyncResult and the resampled Keypoints2D list. After this
         point, frame i means the same instant in every camera.
    """
    raise NotImplementedError
