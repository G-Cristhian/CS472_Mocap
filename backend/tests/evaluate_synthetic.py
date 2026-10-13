"""
Run the pipeline's stages 2 and 3 on the synthetic scene under a range of
camera layouts and noise levels and print one table of errors.

    cd backend
    python -m tests.evaluate_synthetic              # the full table, a few minutes
    python -m tests.evaluate_synthetic --quick      # fewer rows, shorter routine
    python -m tests.evaluate_synthetic --bvh out/synthetic_take.bvh   # also write a BVH for the viewer

Columns: mean reprojection error the calibration reports; MPJPE (mean per
joint position error) against the truth after the best rigid alignment
(pure shape accuracy) and in the pipeline's own world frame (shape plus the
origin and axis convention); the recovered height; the recovered heel
height while standing (true 3 cm); the error of the camera centres.
"""
from __future__ import annotations

import argparse
import time
import warnings

import numpy as np

from mocap_pipeline import config
from mocap_pipeline.joints import JOINT_INDEX, RIG_JOINTS
from mocap_pipeline.stage2_reconstruct import calibrate, scale_floor, smooth, sync, triangulate
from mocap_pipeline.stage3_rig import bvh_writer, rotations, skeleton
from tests import bvh_reader
from tests.synthetic_scene import (PERFORMER_HEIGHT_M, Noise, Routine, Scene, aligned_mpjpe, camera_centre,
                                   joint_errors, mpjpe, project)

REALISTIC = Noise(pixel_sigma=1.5, dropout=0.02, outlier=0.005)


def run_stage2(scene: Scene, intrinsics=None):
    kps = scene.synced_keypoints()
    rig = calibrate.calibrate_rig(kps, intrinsics)
    rough = triangulate.triangulate_sequence(kps, rig)
    rig = scale_floor.make_metric(rig, rough, PERFORMER_HEIGHT_M)
    raw = triangulate.triangulate_sequence(kps, rig)
    return smooth.smooth(smooth.fill_gaps(raw)), rig


def measure(scene: Scene, pose, rig) -> dict:
    truth = scene.truth_in_pipeline_frame()
    al, angle, shift = aligned_mpjpe(pose.points, truth)
    st = slice(0, int(scene.routine.stand_s * config.TARGET_FPS))
    heel = (pose.points[st, JOINT_INDEX["LEFT_HEEL"]] + pose.points[st, JOINT_INDEX["RIGHT_HEEL"]]) / 2
    ear = (pose.points[st, JOINT_INDEX["LEFT_EAR"]] + pose.points[st, JOINT_INDEX["RIGHT_EAR"]]) / 2
    A, origin = scene.pipeline_frame()
    true_c = np.array([(camera_centre(c) - origin) @ A.T for c in scene.rig().cameras])
    est_c = np.array([camera_centre(c) for c in rig.cameras])
    return {
        "calib_px": float(np.mean(list(rig.reprojection_error_px.values()))),
        "aligned_mm": al * 1000,
        "frame_mm": mpjpe(pose.points, truth) * 1000,
        "rot_deg": angle,
        "shift_cm": float(np.linalg.norm(shift)) * 100,
        "height_cm": (np.nanmedian(np.linalg.norm(ear - heel, axis=1)) + config.HEAD_TOP_ABOVE_EARS_M
                      + config.HEEL_ABOVE_FLOOR_M - PERFORMER_HEIGHT_M) * 100,
        "heel_cm": float(np.nanmedian(heel[:, 1])) * 100,
        "cam_cm": float(np.linalg.norm(est_c - true_c, axis=1).mean()) * 100,
        "missing_pct": float(np.isnan(pose.points[..., 0]).mean()) * 100,
    }


HEADER = (f"{'configuration':44s} {'calib px':>8s} {'MPJPE aligned':>13s} {'MPJPE in frame':>14s} {'rot':>5s} {'shift':>6s} "
          f"{'height err':>10s} {'heel y':>6s} {'cam err':>7s} {'missing':>7s} {'time':>5s}")


def row(label: str, m: dict, dt: float) -> str:
    return (f"{label:44s} {m['calib_px']:8.2f} {m['aligned_mm']:10.1f} mm {m['frame_mm']:11.0f} mm {m['rot_deg']:4.1f}° "
            f"{m['shift_cm']:4.0f}cm {m['height_cm']:+8.1f} cm {m['heel_cm']:5.2f} {m['cam_cm']:5.0f}cm {m['missing_pct']:6.2f}% {dt:4.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="shorter routine and fewer configurations")
    parser.add_argument("--bvh", default=None, help="write the final BVH of the 3-camera realistic run here")
    args = parser.parse_args()
    warnings.filterwarnings("ignore")

    routine = Routine(stand_s=2.0, walk_s=6.0, perform_s=3.0) if args.quick else Routine()
    configs = [
        ("3 cams (0,-60,60), no noise", Scene(routine=routine)),
        ("3 cams, 1.5 px noise", Scene(routine=routine, noise=Noise(pixel_sigma=1.5))),
        ("3 cams, 1.5 px + 2% dropout + 0.5% outliers", Scene(routine=routine, noise=REALISTIC)),
        ("3 cams, 3 px + dropout + outliers", Scene(routine=routine, noise=Noise(pixel_sigma=3.0, dropout=0.02, outlier=0.005))),
        ("2 cams (-35,35), realistic", Scene(routine=routine, angles_deg=(-35, 35), noise=REALISTIC)),
        ("4 cams (-20,-65,20,65), realistic", Scene(routine=routine, angles_deg=(-20, -65, 20, 65), noise=REALISTIC)),
    ]
    if not args.quick:
        configs += [
            ("2 cams only 10 deg apart, 1.5 px", Scene(routine=routine, angles_deg=(-5, 5), noise=Noise(pixel_sigma=1.5))),
            ("3 cams at 2.5 m, realistic", Scene(routine=routine, distance_m=2.5, noise=REALISTIC)),
            ("3 cams, cam1 is 75 deg fov processed as 65", Scene(routine=routine, hfov_deg=(65.0, 75.0, 65.0), noise=Noise(pixel_sigma=1.5))),
        ]

    print("\nStage 2 (calibrate from the performer, scale, floor, triangulate, smooth) against the truth\n")
    print(HEADER)
    keep = None
    for label, scene in configs:
        t0 = time.time()
        intrinsics = None
        if "processed as 65" in label:
            intrinsics = [calibrate.initial_intrinsics(scene.width, scene.height, 65.0)] * scene.n_cameras
        pose, rig = run_stage2(scene, intrinsics)
        print(row(label, measure(scene, pose, rig), time.time() - t0))
        if "3 cams, 1.5 px + 2%" in label:
            keep = (scene, pose)

    print("\nStage 2a (sync): resampling each phone onto the shared clock, error in pixels against exact projection\n")
    # clap offsets that are not whole frames at any of these rates, so the shared clock
    # falls between frames and the interpolation is actually exercised
    for fps in ((30.0, 30.0, 30.0), (60.0, 60.0, 60.0), (120.0, 120.0, 120.0)):
        scene = Scene(routine=routine, fps=fps, clap_s=(1.0137, 0.8623, 2.3041))
        rec = scene.recorded_keypoints()
        result, synced = sync.synchronise([k.video_path for k in rec], rec, scene.clap_times())
        worst = 0.0
        means = []
        for k, cam in zip(synced, scene.rig().cameras):
            exact, _ = project(scene.truth(result.common_timestamps), cam, scene.width, scene.height)
            d = np.linalg.norm(k.points - exact, axis=-1)
            worst = max(worst, float(np.nanmax(d)))
            means.append(float(np.nanmean(d)))
        px_per_m = scene.rig().cameras[0].K[0, 0] / scene.distance_m
        print(f"  phones at {fps[0]:.0f} fps -> {config.TARGET_FPS:.0f} fps clock: mean {np.mean(means):.3f} px, "
              f"worst frame {worst:.1f} px (about {worst / px_per_m * 100:.1f} cm at {scene.distance_m:.0f} m)")

    print("\nStage 3 (skeleton, rotations, BVH) on the realistic 3-camera result, read back with forward kinematics\n")
    scene, pose = keep
    rig_pos = skeleton.rig_joint_positions(pose)
    offsets = skeleton.rest_pose_offsets(skeleton.bone_lengths(rig_pos))
    root, local = rotations.solve_rotations(rig_pos, offsets)
    euler = rotations.to_euler_degrees(local, bvh_writer.ROTATION_ORDER)
    path = args.bvh or "/tmp/synthetic_take.bvh"
    bvh_writer.write_bvh(path, offsets, root, euler, pose.fps)
    fk = bvh_reader.joint_positions(path)
    truth_rig = skeleton.rig_joint_positions(scene.truth_pose())
    A, origin = scene.pipeline_frame()
    truth_rig = (truth_rig - origin) @ A.T
    fk_pts = np.stack([fk[n if n in fk else "Neck_end"] for n in RIG_JOINTS], axis=1)
    e_fk = joint_errors(fk_pts, rig_pos)
    al, _, _ = aligned_mpjpe(fk_pts, truth_rig)
    print(f"  BVH forward kinematics vs the rig positions it was built from: mean {np.nanmean(e_fk)*1000:.1f} mm, "
          f"max {np.nanmax(e_fk)*1000:.1f} mm  (fixed bone lengths vs per-frame positions)")
    print(f"  BVH vs the true H36M skeleton after rigid alignment: {al*1000:.1f} mm over {len(RIG_JOINTS)} joints")
    print(f"  wrote {path}")


if __name__ == "__main__":
    main()
