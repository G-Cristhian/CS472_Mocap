"""
The camera placement tool (Rahimian & Kearney 2015) on the synthetic scene's
cameras, where every answer is known from geometry.

A front arc sees the performer's front only: a wall facing away from the arc
hides every camera, so the point error of an arc is at least 180 degrees. A
ring around the performer has a triangulable pair on every side, so its error
is 0. The annealer must turn a random layout into something no worse.
"""
import numpy as np
import pytest

from mocap_pipeline import config
from mocap_pipeline.placement import anneal, metric
from mocap_pipeline.placement.anneal import Constraints
from mocap_pipeline.schemas import CameraRig
from tests.synthetic_scene import Routine, Scene

CENTRE = np.array([0.0, 0.9, 0.0])
SHORT = Routine(stand_s=1.0, walk_s=3.0, perform_s=1.0)


def rig_at(angles_deg, distance_m=4.0) -> CameraRig:
    return Scene(angles_deg=angles_deg, distance_m=distance_m, routine=SHORT).rig()


def ring(n=4, distance_m=4.0) -> CameraRig:
    return rig_at(tuple(360.0 * i / n for i in range(n)), distance_m)


# ---- camera_sees and is_triangulable ---------------------------------------------------------

def test_camera_centre_round_trips_the_scene_placement():
    cam = rig_at((30.0,)).cameras[0]
    expected = np.array([4.0 * np.sin(np.radians(30)), 1.3, 4.0 * np.cos(np.radians(30))])
    assert np.allclose(metric.camera_centre(cam), expected)


def test_camera_sees_in_front_but_not_behind_or_too_far():
    cam = rig_at((0.0,)).cameras[0]
    assert metric.camera_sees(cam, CENTRE)
    assert not metric.camera_sees(cam, CENTRE + [0.0, 0.0, 8.0])        # behind the camera
    assert not metric.camera_sees(cam, CENTRE + [5.0, 0.0, 0.0])        # outside the image
    far = rig_at((0.0,), distance_m=config.CAMERA_EFFECTIVE_RANGE_M + 1.0).cameras[0]
    assert not metric.camera_sees(far, CENTRE)


def test_convergence_angle_matches_the_arc():
    a, b = rig_at((-35.0, 35.0)).cameras
    assert metric.convergence_angle_deg(a, b, CENTRE) == pytest.approx(70.0, abs=0.5)


def test_protocol_arc_is_triangulable_and_narrow_or_opposite_pairs_are_not():
    assert metric.is_triangulable(*rig_at((-35.0, 35.0)).cameras, CENTRE)        # 70 degrees
    assert not metric.is_triangulable(*rig_at((-5.0, 5.0)).cameras, CENTRE)      # 10: under MIN_CONVERGENCE_DEG
    assert not metric.is_triangulable(*rig_at((0.0, 180.0)).cameras, CENTRE)     # 180: over MAX_CONVERGENCE_DEG


# ---- point_error ------------------------------------------------------------------------------

def test_point_error_nobody_or_one_camera():
    nobody = CameraRig(cameras=[], reprojection_error_px={}, is_metric=True)
    assert metric.point_error(nobody, CENTRE) == 360.0 + config.PLACEMENT_UNCOVERED_PENALTY_DEG
    assert metric.point_error(rig_at((0.0,)), CENTRE) == 360.0
    assert metric.point_error(rig_at((0.0, 60.0)), CENTRE + [0.0, 0.0, 9.0]) == 360.0 + config.PLACEMENT_UNCOVERED_PENALTY_DEG


def test_ring_is_perfect_and_front_arc_misses_the_back():
    assert metric.point_error(ring(4), CENTRE) == pytest.approx(0.0, abs=1e-6)
    arc = metric.point_error(rig_at((-60.0, 0.0, 60.0)), CENTRE)
    assert 180.0 <= arc < 360.0


def test_two_cameras_only_ten_degrees_apart_never_triangulate():
    assert metric.point_error(rig_at((-5.0, 5.0)), CENTRE) == pytest.approx(360.0)


def test_wider_arcs_cover_more_wall_orientations():
    narrow = metric.point_error(rig_at((-20.0, 20.0)), CENTRE)      # 40 degrees apart: just triangulable
    wide = metric.point_error(rig_at((-65.0, 65.0)), CENTRE)        # 130 apart
    assert wide < narrow


def test_layout_cost_sums_points_and_target_points_come_from_a_pose_or_a_grid():
    rig = ring(4)
    pts = np.array([CENTRE, CENTRE + [0.3, 0.0, 0.0]])
    assert metric.layout_cost(rig, pts) == pytest.approx(sum(metric.point_error(rig, p) for p in pts))

    grid = metric.target_points_from_pose()
    n = len(np.arange(-config.PLACEMENT_GRID_HALF_WIDTH_M, config.PLACEMENT_GRID_HALF_WIDTH_M + 1e-9, config.PLACEMENT_GRID_STEP_M))
    assert grid.shape == (n * n * len(config.PLACEMENT_GRID_HEIGHTS_M), 3)

    pose = Scene(routine=SHORT).truth_pose()
    sampled = metric.target_points_from_pose(pose, max_points=50)
    assert sampled.shape == (50, 3) and np.isfinite(sampled).all()
    assert np.array_equal(sampled, metric.target_points_from_pose(pose, max_points=50))   # deterministic


# ---- the annealer -------------------------------------------------------------------------------

def test_random_layout_respects_the_constraints():
    c = Constraints(x_range=(-3.0, 3.0), z_range=(-3.0, 3.0), height_range=(1.0, 1.5), min_distance_m=2.0)
    rig = anneal.random_layout(5, c, np.random.default_rng(1))
    assert len(rig.cameras) == 5 and rig.is_metric
    for cam in rig.cameras:
        p = metric.camera_centre(cam)
        assert -3.0 <= p[0] <= 3.0 and 1.0 <= p[1] <= 1.5 and -3.0 <= p[2] <= 3.0
        assert np.hypot(p[0], p[2]) >= 2.0
        assert metric.camera_sees(cam, np.asarray(c.aim))                   # aimed at the centre


def test_optimise_layout_never_returns_worse_than_its_start_and_is_deterministic():
    c = Constraints(x_range=(-3.0, 3.0), z_range=(-3.0, 3.0))
    targets = metric.target_points_from_pose()[::6]                        # a few dozen points
    start = anneal.random_layout(3, c, np.random.default_rng(0))
    before = metric.layout_cost(start, targets)
    best = anneal.optimise_layout(3, c, targets, iterations=150, seed=0, initial=start)
    after = metric.layout_cost(best, targets)
    assert after <= before
    again = anneal.optimise_layout(3, c, targets, iterations=150, seed=0, initial=start)
    assert np.allclose([metric.camera_centre(x) for x in best.cameras], [metric.camera_centre(x) for x in again.cameras])


def test_optimiser_spreads_three_cameras_around_the_performer():
    # with a ring allowed, three cameras should end up far better than a front arc at one point
    c = Constraints(x_range=(-4.0, 4.0), z_range=(-4.0, 4.0), min_distance_m=2.5)
    targets = np.array([CENTRE])
    best = anneal.optimise_layout(3, c, targets, iterations=400, seed=3)
    assert metric.layout_cost(best, targets) < metric.point_error(rig_at((-60.0, 0.0, 60.0)), CENTRE)
