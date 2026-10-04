"""
Command line entry point: runs every stage in order.

    cd backend
    python -m mocap_pipeline.run_pipeline cam0.mp4 cam1.mp4 --height-m 1.75 --out take01.bvh

This file is the one place that knows the order of the stages. When the web
backend is built later, it should call run() rather than repeat this logic.
"""
from __future__ import annotations

import argparse

from . import config
from .stage1_keypoints import detect
from .stage2_reconstruct import calibrate, scale_floor, smooth, sync, triangulate
from .stage3_rig import bvh_writer, rotations, skeleton


def run(video_paths: list[str], performer_height_m: float, out_path: str) -> None:
    if len(video_paths) < 2:
        raise ValueError("At least two videos (two phones) are required.")

    # Stage 1: 2D joints per camera.
    keypoints = [detect.detect_video(v, config.POSE_MODEL_PATH) for v in video_paths]

    # Stage 2a: one shared clock.
    _sync_result, keypoints = sync.synchronise(video_paths, keypoints)

    # Stage 2b: where the cameras are, then real-world units.
    rig = calibrate.calibrate_rig(keypoints)
    rough_pose = triangulate.triangulate_sequence(keypoints, rig)
    rig = scale_floor.make_metric(rig, rough_pose, performer_height_m)

    # Stage 2c: final 3D joints.
    pose = triangulate.triangulate_sequence(keypoints, rig)
    pose = smooth.smooth(smooth.fill_gaps(pose))

    # Stage 3: skeleton rig file.
    rig_positions = skeleton.rig_joint_positions(pose)
    offsets = skeleton.rest_pose_offsets(skeleton.bone_lengths(rig_positions))
    root_positions, local_rotations = rotations.solve_rotations(rig_positions, offsets)
    euler = rotations.to_euler_degrees(local_rotations)
    bvh_writer.write_bvh(out_path, offsets, root_positions, euler, pose.fps)

    # TODO: save every intermediate result with io.py next to out_path so a
    # failed run can be inspected and resumed from the last good stage.


def main() -> None:
    parser = argparse.ArgumentParser(description="Phone videos to BVH skeleton.")
    parser.add_argument("videos", nargs="+",
                        help="One video per phone, two or more. The first is the reference camera.")
    parser.add_argument("--height-m", type=float, required=True,
                        help="Performer height in metres; sets the real-world scale.")
    parser.add_argument("--out", default="out.bvh", help="Output BVH path.")
    args = parser.parse_args()
    run(args.videos, args.height_m, args.out)


if __name__ == "__main__":
    main()
