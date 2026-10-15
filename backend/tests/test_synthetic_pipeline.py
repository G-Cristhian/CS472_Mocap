"""
Stages 2 and 3 on a synthetic performer seen by virtual phones
(tests/synthetic_scene.py), checked against the known truth.

The scene has exact bone lengths and the pipeline's own height rule built
in, so stage output can be compared in millimetres. Thresholds are set from
the measured behaviour (tests/evaluate_synthetic.py prints the full table)
with headroom, so they catch regressions rather than noise.

A short routine keeps each calibration under a few seconds.
"""
import numpy as np
import pytest

from mocap_pipeline import config
from mocap_pipeline.joints import JOINT_INDEX, RIG_JOINTS
from mocap_pipeline.stage2_reconstruct import calibrate, scale_floor, smooth, sync, triangulate
from mocap_pipeline.stage3_rig import bvh_writer, rotations, skeleton
from tests import bvh_reader
from tests.synthetic_scene import (PERFORMER_HEIGHT_M, Noise, Routine, Scene, aligned_mpjpe, camera_centre,
                                   joint_errors, mpjpe, project)

SHORT = Routine(stand_s=2.0, walk_s=6.0, perform_s=3.0)
REALISTIC = Noise(pixel_sigma=1.5, dropout=0.02, outlier=0.005)


def stage2(scene: Scene, intrinsics=None):
    """calibrate -> rough triangulation -> metric -> triangulation -> clean-up, as run_pipeline does."""
    kps = scene.synced_keypoints()
    rig = calibrate.calibrate_rig(kps, intrinsics)
    rough = triangulate.triangulate_sequence(kps, rig)
    rig = scale_floor.make_metric(rig, rough, PERFORMER_HEIGHT_M)
    pose = smooth.smooth(smooth.fill_gaps(triangulate.triangulate_sequence(kps, rig)))
    return pose, rig


def standing_height_and_heel(pose, scene):
    """Height from the heel-ear rule and the heel height, over the standing frames."""
    st = slice(0, int(scene.routine.stand_s * config.TARGET_FPS))
    heel = (pose.points[st, JOINT_INDEX["LEFT_HEEL"]] + pose.points[st, JOINT_INDEX["RIGHT_HEEL"]]) / 2
    ear = (pose.points[st, JOINT_INDEX["LEFT_EAR"]] + pose.points[st, JOINT_INDEX["RIGHT_EAR"]]) / 2
    height = np.nanmedian(np.linalg.norm(ear - heel, axis=1)) + config.HEAD_TOP_ABOVE_EARS_M + config.HEEL_ABOVE_FLOOR_M
    return float(height), float(np.nanmedian(heel[:, 1]))


# ---- the scene itself -------------------------------------------------------------

def test_scene_matches_the_pipelines_height_rule():
    scene = Scene(routine=SHORT)
    height, heel = standing_height_and_heel(scene.truth_pose(), scene)
    assert abs(height - PERFORMER_HEIGHT_M) < 0.001
    assert abs(heel - config.HEEL_ABOVE_FLOOR_M) < 1e-9


def test_scene_bone_lengths_are_constant():
    pts = Scene(routine=SHORT).truth()
    for a, b in [("LEFT_HIP", "LEFT_KNEE"), ("RIGHT_KNEE", "RIGHT_ANKLE"), ("LEFT_SHOULDER", "LEFT_ELBOW"),
                 ("RIGHT_ELBOW", "RIGHT_WRIST"), ("LEFT_HIP", "RIGHT_HIP"), ("LEFT_EAR", "LEFT_SHOULDER")]:
        d = np.linalg.norm(pts[:, JOINT_INDEX[a]] - pts[:, JOINT_INDEX[b]], axis=1)
        assert d.max() - d.min() < 1e-9, (a, b)


def test_scene_is_fully_visible_to_every_camera():
    scene = Scene(routine=SHORT)
    for cam in scene.rig().cameras:
        _, visible = project(scene.truth(), cam, scene.width, scene.height)
        assert visible.all(), cam.camera_id


# ---- stage 2c: triangulation with the true cameras ----------------------------------

def test_triangulation_is_exact_without_noise():
    scene = Scene(routine=SHORT)
    pose = triangulate.triangulate_sequence(scene.synced_keypoints(), scene.rig())
    err = joint_errors(pose.points, scene.truth())
    assert not np.isnan(err).any()
    assert np.nanmax(err) < 1e-4
    assert (pose.num_views == 3).all()


def test_triangulation_error_scales_with_pixel_noise():
    small = Scene(routine=SHORT, noise=Noise(pixel_sigma=1.5))
    large = Scene(routine=SHORT, noise=Noise(pixel_sigma=3.0))
    e_small = mpjpe(triangulate.triangulate_sequence(small.synced_keypoints(), small.rig()).points, small.truth())
    e_large = mpjpe(triangulate.triangulate_sequence(large.synced_keypoints(), large.rig()).points, large.truth())
    assert e_small < 0.008            # measured about 4.6 mm at 1.5 px, 4 m away
    assert 1.5 < e_large / e_small < 2.5


def test_three_cameras_reject_a_single_outlier_view():
    scene = Scene(routine=SHORT, noise=Noise(pixel_sigma=1.0, outlier=0.01, outlier_px=60.0))
    pose = triangulate.triangulate_sequence(scene.synced_keypoints(), scene.rig())
    err = joint_errors(pose.points, scene.truth())
    # an undetected 60 px outlier in one of three views would move the joint by centimetres
    assert np.nanquantile(err, 0.99) < 0.02
    assert np.isnan(err).mean() < 0.01


# ---- stage 2b + 2c: calibration from the performer, scale and floor ----------------------

def test_full_stage2_without_noise_recovers_the_truth():
    scene = Scene(routine=SHORT)
    pose, rig = stage2(scene)
    al, _, _ = aligned_mpjpe(pose.points, scene.truth_in_pipeline_frame())
    height, heel = standing_height_and_heel(pose, scene)
    assert al < 0.003
    assert abs(height - PERFORMER_HEIGHT_M) < 0.005
    assert abs(heel - config.HEEL_ABOVE_FLOOR_M) < 0.005
    assert rig.is_metric
    assert max(rig.reprojection_error_px.values()) < 0.1


@pytest.mark.parametrize("angles", [(0, -60, 60), (-35, 35), (-20, -65, 20, 65)])
def test_full_stage2_with_realistic_noise(angles):
    scene = Scene(routine=SHORT, angles_deg=angles, noise=REALISTIC)
    pose, rig = stage2(scene)
    truth = scene.truth_in_pipeline_frame()
    al, _, shift = aligned_mpjpe(pose.points, truth)
    height, heel = standing_height_and_heel(pose, scene)
    assert al < 0.012, "shape error after rigid alignment"
    assert abs(height - PERFORMER_HEIGHT_M) < 0.01
    assert abs(heel - config.HEEL_ABOVE_FLOOR_M) < 0.015
    assert np.mean(list(rig.reprojection_error_px.values())) < 3.0
    # the up axis: recovered standing heel-to-ear direction is vertical
    st = slice(0, int(scene.routine.stand_s * config.TARGET_FPS))
    axis = np.nanmean(pose.points[st, JOINT_INDEX["LEFT_EAR"]] - pose.points[st, JOINT_INDEX["LEFT_HEEL"]], axis=0)
    assert np.degrees(np.arccos(axis[1] / np.linalg.norm(axis))) < 2.0
    # the origin: documented as "under the middle of the performer's footprint". estimate_floor
    # puts it at the mean of the lowest 20% of foot points, which lands on whichever side of the
    # walking area the preliminary up vector tilts towards (see evaluate_synthetic.py), so only
    # check it stays within the area the performer used.
    assert np.linalg.norm(shift) < 2.0 * scene.routine.walk_radius_m + 0.5
    # camera 0 is on the +Z side, at about its true distance from the performer
    c0 = camera_centre(rig.cameras[0])
    assert c0[2] > 0 and abs(np.linalg.norm(c0) - np.linalg.norm(camera_centre(scene.rig().cameras[0]))) < 1.5


def test_narrow_baseline_is_much_worse_than_the_protocol_arc():
    narrow = Scene(routine=SHORT, angles_deg=(-5, 5), noise=Noise(pixel_sigma=1.5))
    wide = Scene(routine=SHORT, angles_deg=(-35, 35), noise=Noise(pixel_sigma=1.5))
    e_narrow, _, _ = aligned_mpjpe(stage2(narrow)[0].points, narrow.truth_in_pipeline_frame())
    e_wide, _, _ = aligned_mpjpe(stage2(wide)[0].points, wide.truth_in_pipeline_frame())
    assert e_narrow > 3 * e_wide


def test_wrong_field_of_view_costs_accuracy_but_still_runs():
    # a Galaxy Fold at 75 degrees processed with the default 65 (protocol section 3)
    scene = Scene(routine=SHORT, hfov_deg=(65.0, 75.0, 65.0), noise=Noise(pixel_sigma=1.5))
    assumed = [calibrate.initial_intrinsics(scene.width, scene.height, 65.0)] * 3
    pose, rig = stage2(scene, assumed)
    al, _, _ = aligned_mpjpe(pose.points, scene.truth_in_pipeline_frame())
    assert al < 0.05
    assert np.mean(list(rig.reprojection_error_px.values())) > 1.5   # the mismatch shows up in the error number


def test_standing_still_only_fails_calibration_with_the_documented_message():
    scene = Scene(routine=Routine(stand_s=4.0, walk_s=0.0, perform_s=0.0), noise=Noise(pixel_sigma=1.0))
    with pytest.raises(calibrate.CalibrationError, match="move around more"):
        calibrate.calibrate_rig(scene.synced_keypoints())


def test_feet_out_of_frame_fail_the_scale_step():
    # cameras mounted high and aimed level, so the feet stay below the bottom edge of every
    # image even at the far side of the walk, where the view is widest
    scene = Scene(routine=SHORT, camera_height_m=2.3, aim=(0.0, 2.3, 0.0), noise=Noise(pixel_sigma=1.0))
    kps = scene.synced_keypoints()
    assert all(np.isnan(k.points[:, JOINT_INDEX["LEFT_HEEL"]]).all() for k in kps)
    rig = calibrate.calibrate_rig(kps)
    rough = triangulate.triangulate_sequence(kps, rig)
    with pytest.raises(ValueError, match="upright|feet"):
        scale_floor.make_metric(rig, rough, PERFORMER_HEIGHT_M)


# ---- stage 2a: sync's resampling ---------------------------------------------------------

def test_sync_resamples_mixed_frame_rates_onto_one_clock():
    scene = Scene(routine=SHORT, fps=(60.0, 30.0, 30.0), clap_s=(1.0, 0.85, 2.3))
    recorded = scene.recorded_keypoints()
    result, synced = sync.synchronise([k.video_path for k in recorded], recorded, scene.clap_times())
    times = result.common_timestamps
    assert abs(times[1] - times[0] - 1 / config.TARGET_FPS) < 1e-9
    assert abs(times[-1] - (scene.routine.duration - 1 / config.TARGET_FPS)) < 0.05
    for k, cam in zip(synced, scene.rig().cameras):
        exact, _ = project(scene.truth(times), cam, scene.width, scene.height)
        d = np.linalg.norm(k.points - exact, axis=-1)
        assert np.nanmean(d) < 0.5            # linear interpolation between frames
        assert np.nanmax(d) < 8.0             # the fastest punch frames, 30 fps camera off the grid (measured 4 px)
        assert np.isnan(d).mean() < 0.005


# ---- stage 3: skeleton, rotations and the BVH file --------------------------------------

def test_bvh_round_trip_reproduces_the_rig_positions(tmp_path):
    pose = Scene(routine=SHORT).truth_pose()
    rig_pos = skeleton.rig_joint_positions(pose)
    offsets = skeleton.rest_pose_offsets(skeleton.bone_lengths(rig_pos))
    root, local = rotations.solve_rotations(rig_pos, offsets)
    euler = rotations.to_euler_degrees(local, bvh_writer.ROTATION_ORDER)
    path = tmp_path / "truth.bvh"
    bvh_writer.write_bvh(str(path), offsets, root, euler, pose.fps)

    fk = bvh_reader.joint_positions(str(path))
    for j, name in enumerate(RIG_JOINTS):
        key = name if name in fk else "Neck_end"     # Head is written as the End Site of Neck
        assert np.linalg.norm(fk[key] - rig_pos[:, j], axis=1).max() < 1e-4, name


def test_bone_lengths_from_the_scene_are_symmetric_and_exact():
    lengths = skeleton.bone_lengths(skeleton.rig_joint_positions(Scene(routine=SHORT).truth_pose()))
    assert abs(lengths["LeftKnee"] - 0.42) < 1e-6 and abs(lengths["RightKnee"] - 0.42) < 1e-6
    assert abs(lengths["LeftElbow"] - 0.28) < 1e-6 and abs(lengths["LeftWrist"] - 0.26) < 1e-6
    assert abs(lengths["RightHip"] - 0.10) < 1e-6


# ---- the whole pipeline through run_pipeline.run() ---------------------------------------

def test_run_pipeline_end_to_end_on_the_synthetic_scene(tmp_path, monkeypatch):
    """
    Stage 1 is replaced by the scene's observations (different frame rates and
    start times per phone); sync is given the clap times; everything after
    that is the real pipeline, down to the JSON and BVH files.
    """
    from mocap_pipeline import run_pipeline
    from mocap_pipeline.stage1_keypoints import detect

    scene = Scene(routine=SHORT, fps=(60.0, 30.0, 30.0), clap_s=(1.0, 0.85, 2.3), noise=REALISTIC)
    recorded = {k.video_path: k for k in scene.recorded_keypoints(str(tmp_path))}
    for path in recorded:
        (tmp_path / path.split("/")[-1]).write_bytes(b"stand-in for a phone video")
    monkeypatch.setattr(detect, "detect_video", lambda video_path, model_path, detector="mediapipe": recorded[str(video_path)])

    out = tmp_path / "output" / "take.json"
    run_pipeline.run(list(recorded), str(out), performer_height_m=PERFORMER_HEIGHT_M, model_path="unused",
                     camera=["webcam"] * 3, fov=[65.0] * 3, clap_times=scene.clap_times(),
                     calibration_path=str(tmp_path / "output" / "calibration.json"))

    assert out.exists() and out.with_suffix(".bvh").exists()
    import json
    frames = json.load(open(out))
    assert abs(frames[1]["t"] - frames[0]["t"] - 1 / config.TARGET_FPS) < 1e-3   # t is written with 4 decimals
    assert len(frames) == len(scene.common_times()) or abs(len(frames) - len(scene.common_times())) <= 1
    # the JSON joints against the truth, shape only
    est = np.array([[np.nan] * 3 if f["landmarks"][n] is None else [f["landmarks"][n][k] for k in "xyz"]
                    for f in frames for n in scene_joint_names()]).reshape(len(frames), -1, 3)
    truth = scene.truth(np.array([f["t"] for f in frames]))
    al, _, _ = aligned_mpjpe(est, truth)
    assert al < 0.015
    # the BVH, read back with forward kinematics, against the true H36M skeleton
    fk = bvh_reader.joint_positions(str(out.with_suffix(".bvh")))
    fk_pts = np.stack([fk[n if n in fk else "Neck_end"] for n in RIG_JOINTS], axis=1)
    truth_rig = skeleton.rig_joint_positions(scene.truth_pose(np.array([f["t"] for f in frames])))
    al_bvh, _, _ = aligned_mpjpe(fk_pts, truth_rig)
    assert al_bvh < 0.03
    # resume works on the files it just wrote
    run_pipeline.run(list(recorded), str(out), performer_height_m=PERFORMER_HEIGHT_M, model_path="unused",
                     camera=["webcam"] * 3, fov=[65.0] * 3, clap_times=scene.clap_times(),
                     calibration_path=str(tmp_path / "output" / "calibration.json"), resume=True)


def scene_joint_names():
    from mocap_pipeline.joints import MEDIAPIPE_JOINTS
    return MEDIAPIPE_JOINTS
