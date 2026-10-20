"""
MediaPipe runs give the same 3D result as before the joint list grew past
MediaPipe's 33 (joints.EXTRA_JOINTS, filled by RTMPose only).

The reference file holds what the 33-joint pipeline (commit 8596016) wrote
for the synthetic end-to-end run: the 3D joints and the BVH on every 10th
frame, the scale and the bone lengths. It was written with

    cd backend
    python -m tests.test_mediapipe_parity --write

Rewrite it the same way only when a change is meant to alter MediaPipe's
result (say so in the commit). aniposelib's bundle adjustment samples points
with numpy's global random generator, so the run seeds it first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REFERENCE = Path(__file__).parent / "data" / "mediapipe_synthetic_reference.json"
EVERY = 10          # keep every 10th frame in the reference


def run_synthetic(tmp_path: Path) -> dict:
    """
    run_pipeline.run() on the synthetic scene as test_synthetic_pipeline's
    end-to-end test does (stage 1 replaced by the scene's MediaPipe-style
    observations), reduced to the numbers kept in the reference file.
    """
    from mocap_pipeline import run_pipeline
    from mocap_pipeline.joints import MEDIAPIPE_JOINTS
    from mocap_pipeline.stage1_keypoints import detect
    from tests.synthetic_scene import PERFORMER_HEIGHT_M, Noise, Routine, Scene

    scene = Scene(routine=Routine(stand_s=2.0, walk_s=6.0, perform_s=3.0), fps=(60.0, 30.0, 30.0),
                  clap_s=(1.0, 0.85, 2.3), noise=Noise(pixel_sigma=1.5, dropout=0.02, outlier=0.005))
    recorded = {k.video_path: k for k in scene.recorded_keypoints(str(tmp_path))}
    for path in recorded:
        Path(path).write_bytes(b"stand-in for a phone video")

    out = tmp_path / "output" / "take.json"
    real_detect = detect.detect_video
    detect.detect_video = lambda video_path, model_path, detector="mediapipe": recorded[str(video_path)]
    np.random.seed(0)
    try:
        run_pipeline.run(list(recorded), str(out), performer_height_m=PERFORMER_HEIGHT_M, model_path="unused",
                         camera=["webcam"] * 3, fov=[65.0] * 3, clap_times=scene.clap_times(),
                         calibration_path=str(tmp_path / "output" / "calibration.json"), jobs=1)
    finally:
        detect.detect_video = real_detect

    frames = json.loads(out.read_text())
    metrics = json.loads(out.with_suffix(".metrics.json").read_text())
    bvh = out.with_suffix(".bvh").read_text().splitlines()
    motion = bvh.index("MOTION")

    return {
        "frames": len(frames),
        "metres_per_unit": metrics["scale"]["metres_per_unit"],
        "bone_lengths_m": {b: v["median_m"] for b, v in metrics["rig"]["bone_lengths"]["per_bone"].items()},
        "landmarks": {n: [f["landmarks"][n] and [f["landmarks"][n][k] for k in "xyz"] for f in frames[::EVERY]]
                      for n in MEDIAPIPE_JOINTS},
        "bvh_hierarchy": [line.strip() for line in bvh[:motion] if line.strip() and not line.strip().startswith("OFFSET")],
        "bvh_offsets": [[float(v) for v in line.split()[1:]] for line in bvh[:motion] if line.strip().startswith("OFFSET")],
        "bvh_motion": [[float(v) for v in line.split()] for line in bvh[motion + 3:][::EVERY]],
        "_all_landmark_names": list(frames[0]["landmarks"]),
    }


def _close(a, b, atol):
    np.testing.assert_allclose(np.array(a, dtype=float), np.array(b, dtype=float), atol=atol, rtol=0)


def test_mediapipe_result_matches_the_33_joint_pipeline(tmp_path):
    from mocap_pipeline.joints import EXTRA_JOINTS, MEDIAPIPE_JOINTS

    reference = json.loads(REFERENCE.read_text())
    result = run_synthetic(tmp_path)

    assert result["frames"] == reference["frames"]
    assert result["bvh_hierarchy"] == reference["bvh_hierarchy"]
    assert abs(result["metres_per_unit"] / reference["metres_per_unit"] - 1) < 1e-7
    assert result["bone_lengths_m"].keys() == reference["bone_lengths_m"].keys()
    for bone, length in reference["bone_lengths_m"].items():
        assert abs(result["bone_lengths_m"][bone] - length) < 1e-7, bone
    # out3d.json is written in metres with 4 decimals, the BVH in cm and degrees with 6
    for name in MEDIAPIPE_JOINTS:
        ours, theirs = result["landmarks"][name], reference["landmarks"][name]
        assert [p is None for p in ours] == [p is None for p in theirs], name
        _close([p for p in ours if p], [p for p in theirs if p], atol=1.5e-4)
    _close(result["bvh_offsets"], reference["bvh_offsets"], atol=2e-6)
    _close(result["bvh_motion"], reference["bvh_motion"], atol=2e-6)
    # the new joints are written after the 33, and MediaPipe never has them
    assert result["_all_landmark_names"] == MEDIAPIPE_JOINTS + EXTRA_JOINTS


if __name__ == "__main__":
    import tempfile

    if "--write" not in sys.argv:
        sys.exit("usage: python -m tests.test_mediapipe_parity --write   (rewrites the reference file)")
    with tempfile.TemporaryDirectory() as tmp:
        result = run_synthetic(Path(tmp))
    result.pop("_all_landmark_names")
    REFERENCE.parent.mkdir(exist_ok=True)
    REFERENCE.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(f"Wrote {REFERENCE}")
