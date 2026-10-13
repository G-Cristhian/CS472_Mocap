"""Shared helpers: small synthetic schemas objects, no videos or models needed."""
import numpy as np
import pytest

from mocap_pipeline.joints import NUM_JOINTS
from mocap_pipeline.schemas import Camera, CameraRig, Keypoints2D, Pose3D, SyncResult


def make_keypoints(camera_id="cam0", video_path="cam0.mp4", frames=12, seed=0) -> Keypoints2D:
    rng = np.random.default_rng(seed)
    points = rng.uniform(0, 1000, size=(frames, NUM_JOINTS, 2))
    points[3, 5] = np.nan                      # a missing joint survives the round trip
    confidence = rng.uniform(0, 1, size=(frames, NUM_JOINTS))
    confidence[3, 5] = 0.0
    return Keypoints2D(camera_id=camera_id, video_path=video_path, width=1920, height=1080, fps=29.97,
                       timestamps=np.arange(frames) / 29.97, points=points, confidence=confidence)


def make_sync(ids=("cam0", "cam1"), frames=10) -> SyncResult:
    return SyncResult(clap_time_s={cid: 1.0 + 0.25 * i for i, cid in enumerate(ids)},
                      common_timestamps=np.arange(frames) / 30.0)


def make_rig(ids=("cam0", "cam1")) -> CameraRig:
    cams = []
    for i, cid in enumerate(ids):
        K = np.array([[1000.0, 0, 960], [0, 1000.0, 540], [0, 0, 1]])
        angle = 0.3 * i
        R = np.array([[np.cos(angle), 0, np.sin(angle)], [0, 1, 0], [-np.sin(angle), 0, np.cos(angle)]])
        t = np.array([0.5 * i, 0.0, 3.0])
        cams.append(Camera(camera_id=cid, K=K, R=R, t=t))
    return CameraRig(cameras=cams, reprojection_error_px={cid: 1.5 for cid in ids}, is_metric=True)


def make_pose(frames=10, seed=1) -> Pose3D:
    rng = np.random.default_rng(seed)
    points = rng.normal(size=(frames, NUM_JOINTS, 3))
    num_views = rng.integers(0, 4, size=(frames, NUM_JOINTS))
    points[num_views == 0] = np.nan
    return Pose3D(fps=30.0, points=points, num_views=num_views)


@pytest.fixture
def fake_videos(tmp_path):
    """Two small files standing in for videos; only their size and mtime matter."""
    paths = []
    for name in ("cam0.mp4", "cam1.mp4"):
        p = tmp_path / name
        p.write_bytes(b"not really a video " + name.encode())
        paths.append(str(p))
    return paths
