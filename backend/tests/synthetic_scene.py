"""
A synthetic performer and virtual phones, for testing stages 2 and 3 without
footage.

The performer is an articulated figure with the 33 MediaPipe joints and
exactly fixed bone lengths, built so that the pipeline's height rule holds
exactly: ears sit HEAD_TOP_ABOVE_EARS_M below the top of the head and the
heel landmarks HEEL_ABOVE_FLOOR_M above the floor (both from config). It
performs the field test routine (docs/procedures/filming.md, section 5):
stand still, walk a loop with the arms raised and the body turning, then a
fast punching sequence.

World frame is the pipeline's own: metres, Y up, floor at Y = 0, Z pointing
from the performer towards the camera arc, X to the right as seen from
there. Cameras are pinhole phones (OpenCV convention, x_cam = R X + t) in an
arc in front of the performer, like the protocol describes.

Observations are what stage 1 would produce: pixels plus a confidence per
joint, with optional Gaussian pixel noise, dropouts and outliers. Each
camera can have its own frame rate and its own start time before the clap,
so the sync stage can be exercised as well.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from mocap_pipeline import config
from mocap_pipeline.joints import JOINT_INDEX, NUM_JOINTS
from mocap_pipeline.schemas import Camera, CameraRig, Keypoints2D, Pose3D
from mocap_pipeline.stage2_reconstruct.calibrate import initial_intrinsics

# ---- the performer -------------------------------------------------------------

PERFORMER_HEIGHT_M = 1.75
HEEL_Y = config.HEEL_ABOVE_FLOOR_M                            # heel landmark height when standing
EAR_Y = PERFORMER_HEIGHT_M - config.HEAD_TOP_ABOVE_EARS_M     # ear height when standing
HIP_Y, SHOULDER_Y = 0.93, 1.43
HIP_HALF, SHOULDER_HALF, EAR_HALF = 0.10, 0.19, 0.075
THIGH, SHIN, UPPER_ARM, FOREARM = 0.42, 0.42, 0.28, 0.26
ANKLE_Y = HIP_Y - THIGH - SHIN                                # 0.09 when standing
ANKLE_ABOVE_HEEL = ANKLE_Y - HEEL_Y

FOOT_JOINTS = ["LEFT_HEEL", "RIGHT_HEEL", "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX"]


def _rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _unit(v):
    return np.asarray(v, dtype=float) / np.linalg.norm(v)


def _body(theta_l, theta_r, knee_l, knee_r, abduction, flex_r, elbow_l, elbow_r):
    """
    The 33 joints in the body frame: origin on the floor under the pelvis,
    +Y up, +Z the way the performer faces, +X the performer's left.
      theta_*    thigh swing forward (radians), knee_* knee bend
      abduction  both arms raised sideways (0 hanging, pi/2 out, pi up)
      flex_r     right arm raised forward (a punch), used when abduction is 0
      elbow_*    elbow bend, forearm folding forward
    Every bone length is constant whatever the angles.
    """
    p = np.zeros((NUM_JOINTS, 3))

    def put(name, xyz):
        p[JOINT_INDEX[name]] = xyz

    # torso and head: rigid
    put("LEFT_HIP", (HIP_HALF, HIP_Y, 0)); put("RIGHT_HIP", (-HIP_HALF, HIP_Y, 0))
    put("LEFT_SHOULDER", (SHOULDER_HALF, SHOULDER_Y, 0)); put("RIGHT_SHOULDER", (-SHOULDER_HALF, SHOULDER_Y, 0))
    put("LEFT_EAR", (EAR_HALF, EAR_Y, 0)); put("RIGHT_EAR", (-EAR_HALF, EAR_Y, 0))
    put("NOSE", (0, EAR_Y - 0.045, 0.10))
    for side, s in (("LEFT", 1), ("RIGHT", -1)):
        put(f"{side}_EYE_INNER", (s * 0.03, EAR_Y - 0.01, 0.085))
        put(f"{side}_EYE", (s * 0.045, EAR_Y - 0.01, 0.08))
        put(f"{side}_EYE_OUTER", (s * 0.06, EAR_Y - 0.01, 0.07))
        put(f"MOUTH_{side}", (s * 0.025, EAR_Y - 0.075, 0.085))

    # legs: thigh swings about the hip, shin about the knee
    for side, theta, knee in (("LEFT", theta_l, knee_l), ("RIGHT", theta_r, knee_r)):
        hip = p[JOINT_INDEX[f"{side}_HIP"]]
        knee_pos = hip + THIGH * np.array([0, -np.cos(theta), np.sin(theta)])
        shin_angle = theta - knee
        ankle = knee_pos + SHIN * np.array([0, -np.cos(shin_angle), np.sin(shin_angle)])
        # the foot stays flat (heel and toe level), so a lifted foot never dips below the floor
        put(f"{side}_KNEE", knee_pos)
        put(f"{side}_ANKLE", ankle)
        put(f"{side}_HEEL", ankle + np.array([0, -ANKLE_ABOVE_HEEL, -0.03]))
        put(f"{side}_FOOT_INDEX", ankle + np.array([0, -ANKLE_ABOVE_HEEL, 0.15]))

    # arms
    for side, s, flex, elbow in (("LEFT", 1, 0.0, elbow_l), ("RIGHT", -1, flex_r, elbow_r)):
        shoulder = p[JOINT_INDEX[f"{side}_SHOULDER"]]
        if abduction > 1e-9:
            d_upper = np.array([s * np.sin(abduction), -np.cos(abduction), 0.0])
        else:
            d_upper = np.array([0.0, -np.cos(flex), np.sin(flex)])
        d_fore = _rx(-elbow) @ d_upper
        elbow_pos = shoulder + UPPER_ARM * d_upper
        wrist = elbow_pos + FOREARM * d_fore
        # a hand that turns smoothly with the forearm: the reference direction is skewed
        # so the forearm never lines up with it and the hand never flips
        n = _unit(np.cross(d_fore, _unit([1.0, 2.0, 3.0])))
        put(f"{side}_ELBOW", elbow_pos)
        put(f"{side}_WRIST", wrist)
        put(f"{side}_INDEX", wrist + 0.09 * d_fore + 0.02 * n)
        put(f"{side}_PINKY", wrist + 0.08 * d_fore - 0.03 * n)
        put(f"{side}_THUMB", wrist + 0.05 * d_fore + 0.04 * n)

    return p


@dataclass(frozen=True)
class Routine:
    """The recording routine, in seconds. t = 0 is the clap."""
    stand_s: float = 3.0        # still, upright, facing the cameras (sets the height)
    walk_s: float = 12.0        # a loop around the space, arms raised, turning (calibrates)
    perform_s: float = 10.0     # punches, two a second (the take)
    walk_radius_m: float = 0.9

    @property
    def duration(self) -> float:
        return self.stand_s + self.walk_s + self.perform_s


def pose_at(t: float, routine: Routine = Routine()) -> np.ndarray:
    """The 33 joints (metres, world frame) at time t seconds after the clap."""
    if t < routine.stand_s:
        body, yaw, pos = _body(0, 0, 0, 0, 0, 0, 0, 0), 0.0, (0.0, 0.0)
    elif t < routine.stand_s + routine.walk_s:
        # a loop that starts and ends on the spot where the performer stood, so
        # every joint moves continuously through the phase changes
        u = t - routine.stand_s
        phi = 2 * np.pi * u / routine.walk_s
        r = routine.walk_radius_m
        pos = (r * np.sin(phi), r * (np.cos(phi) - 1.0))
        # whole numbers of cycles in the walk, so arms, turning and steps all return to
        # the standing pose when the walk ends
        w = routine.walk_s
        turns, steps, arm_cycles = max(1, round(w / 6.0)), max(1, round(w)), max(1, round(w / 4.0))
        yaw = 0.8 * np.sin(2 * np.pi * u * turns / w)                  # turning left and right
        step = 2 * np.pi * u * steps / w                                # about one step a second
        theta = 0.4 * np.sin(step)
        abduction = 1.2 * (1 - np.cos(2 * np.pi * u * arm_cycles / w)) # arms from hanging to nearly up
        body = _body(theta, -theta, 0.6 * max(0.0, np.sin(step)), 0.6 * max(0.0, -np.sin(step)),
                     abduction, 0, 0, 0)
    else:
        u = t - routine.stand_s - routine.walk_s
        guard = (np.pi / 2) * min(1.0, u / 0.5)                        # forearms come up over half a second
        flex = 0.7 * (1 - np.cos(2 * np.pi * 2.0 * u))                 # right arm forward, 0 to 80 degrees
        body = _body(0, 0, 0, 0, 0, flex, guard, guard * (1 - flex / 1.4))
        yaw, pos = 0.15 * np.sin(2 * np.pi * 2.0 * u), (0.0, 0.0)

    return body @ _ry(yaw).T + np.array([pos[0], 0.0, pos[1]])


def truth(times, routine: Routine = Routine()) -> np.ndarray:
    """(F, 33, 3) joints at the given times."""
    return np.stack([pose_at(float(t), routine) for t in times])


# ---- the cameras ---------------------------------------------------------------

def look_at_camera(camera_id: str, position, aim, K) -> Camera:
    """A camera at `position` looking at `aim`, image x to the right, y down (OpenCV)."""
    position = np.asarray(position, dtype=float)
    forward = _unit(np.asarray(aim, dtype=float) - position)
    right = _unit(np.cross(forward, [0, 1.0, 0]))
    down = np.cross(forward, right)
    R = np.array([right, down, forward])
    return Camera(camera_id=camera_id, K=np.asarray(K, dtype=float), R=R, t=-R @ position)


def camera_centre(cam: Camera) -> np.ndarray:
    return -cam.R.T @ cam.t


def project(points, cam: Camera, width: int, height: int):
    """
    (..., 3) world points -> (..., 2) pixels and a visibility mask. NaN where
    the point is behind the camera or outside the image.
    """
    X = np.asarray(points) @ cam.R.T + cam.t
    z = X[..., 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = cam.K[0, 0] * X[..., 0] / z + cam.K[0, 2]
        v = cam.K[1, 1] * X[..., 1] / z + cam.K[1, 2]
    px = np.stack([u, v], axis=-1)
    visible = (z > 0.1) & (u >= 0) & (u < width) & (v >= 0) & (v < height) & np.isfinite(u) & np.isfinite(v)
    px[~visible] = np.nan
    return px, visible


@dataclass(frozen=True)
class Noise:
    """What stage 1 adds to perfect pixels."""
    pixel_sigma: float = 0.0     # Gaussian noise, pixels
    dropout: float = 0.0         # fraction of visible joints lost (NaN, confidence 0)
    outlier: float = 0.0         # fraction of visible joints displaced by outlier_px, confidence kept
    outlier_px: float = 40.0


def observe(points3d, cam: Camera, width: int, height: int, noise: Noise, rng: np.random.Generator):
    """Pixels and confidence (F, J, 2) / (F, J) for one camera."""
    px, visible = project(points3d, cam, width, height)
    confidence = np.where(visible, rng.uniform(0.85, 1.0, visible.shape), 0.0)
    if noise.pixel_sigma > 0:
        px = px + rng.normal(0.0, noise.pixel_sigma, px.shape)
    if noise.outlier > 0:
        hit = visible & (rng.random(visible.shape) < noise.outlier)
        angle = rng.uniform(0, 2 * np.pi, hit.sum())
        px[hit] += noise.outlier_px * np.stack([np.cos(angle), np.sin(angle)], axis=-1)
    if noise.dropout > 0:
        lost = visible & (rng.random(visible.shape) < noise.dropout)
        px[lost] = np.nan
        confidence[lost] = 0.0
    return px, confidence


# ---- a whole scene -------------------------------------------------------------

def _per_camera(value, n):
    return list(value) if isinstance(value, (list, tuple)) else [value] * n


@dataclass
class Scene:
    """Performer + phones. Camera 0 is the first angle, as in the pipeline."""
    angles_deg: tuple = (0.0, -60.0, 60.0)      # around the performer, 0 = straight ahead
    distance_m: float = 4.0
    camera_height_m: float = 1.3
    aim: tuple = (0.0, 0.9, 0.0)
    hfov_deg: float | tuple = 65.0               # one value or one per camera
    width: int = 1920
    height: int = 1080
    fps: float | tuple = 30.0                    # one value or one per camera
    clap_s: float | tuple = 1.0                  # seconds each video runs before the clap
    noise: Noise = field(default_factory=Noise)
    routine: Routine = field(default_factory=Routine)
    seed: int = 0

    @property
    def n_cameras(self) -> int:
        return len(self.angles_deg)

    def rig(self) -> CameraRig:
        """The true cameras, in the pipeline's world frame (metric)."""
        cams = []
        for i, (a, hfov) in enumerate(zip(self.angles_deg, _per_camera(self.hfov_deg, self.n_cameras))):
            a = np.radians(a)
            position = (self.distance_m * np.sin(a), self.camera_height_m, self.distance_m * np.cos(a))
            cams.append(look_at_camera(f"cam{i}", position, self.aim, initial_intrinsics(self.width, self.height, hfov)))
        return CameraRig(cameras=cams, reprojection_error_px={c.camera_id: 0.0 for c in cams}, is_metric=True)

    def common_times(self) -> np.ndarray:
        """The pipeline's shared timeline for this routine."""
        return np.arange(0.0, self.routine.duration - 1e-9, 1.0 / config.TARGET_FPS)

    def truth(self, times=None) -> np.ndarray:
        return truth(self.common_times() if times is None else times, self.routine)

    def truth_pose(self, times=None) -> Pose3D:
        pts = self.truth(times)
        return Pose3D(fps=config.TARGET_FPS, points=pts, num_views=np.full(pts.shape[:2], self.n_cameras))

    def _rng(self, camera_index: int) -> np.random.Generator:
        return np.random.default_rng(self.seed * 1000 + camera_index)

    def synced_keypoints(self, video_dir: str = "") -> list[Keypoints2D]:
        """Keypoints already on the shared timeline, as if sync had run (bypasses stage 2a)."""
        times = self.common_times()
        pts3 = self.truth(times)
        out = []
        for i, cam in enumerate(self.rig().cameras):
            px, conf = observe(pts3, cam, self.width, self.height, self.noise, self._rng(i))
            out.append(Keypoints2D(camera_id=cam.camera_id, video_path=str(Path(video_dir) / f"{cam.camera_id}.mp4"),
                                   width=self.width, height=self.height, fps=config.TARGET_FPS,
                                   timestamps=times.copy(), points=px, confidence=conf))
        return out

    def recorded_keypoints(self, video_dir: str = "") -> list[Keypoints2D]:
        """
        Keypoints as stage 1 would produce them from each phone's own video:
        its own frame rate, starting clap_s seconds before the clap, timestamps
        counted from the start of its video.
        """
        out = []
        fps_list = _per_camera(self.fps, self.n_cameras)
        clap_list = _per_camera(self.clap_s, self.n_cameras)
        for i, cam in enumerate(self.rig().cameras):
            fps, clap = fps_list[i], clap_list[i]
            world_times = np.arange(-clap, self.routine.duration - 1e-9, 1.0 / fps)
            px, conf = observe(self.truth(world_times), cam, self.width, self.height, self.noise, self._rng(i))
            out.append(Keypoints2D(camera_id=cam.camera_id, video_path=str(Path(video_dir) / f"{cam.camera_id}.mp4"),
                                   width=self.width, height=self.height, fps=fps,
                                   timestamps=world_times + clap, points=px, confidence=conf))
        return out

    def clap_times(self) -> list[float]:
        return [float(c) for c in _per_camera(self.clap_s, self.n_cameras)]

    def pipeline_frame(self):
        """
        Where scale_floor.make_metric says it puts the world: Y up, origin on
        the floor under the middle of the performer's footprint (the planted
        feet, HEEL_ABOVE_FLOOR_M below them), Z towards camera 0 along the
        floor. Returns (A, origin) with A's rows the new axes, so that
        X_pipeline = (X - origin) @ A.T.

        estimate_floor picks "the lowest 20% of foot points" with a
        preliminary up vector; a tilt of that vector by well under a degree is
        enough to make the far side of the walk look lowest, so the pipeline's
        actual origin can sit a metre from this one (see evaluate_synthetic.py).
        """
        pts = self.truth()
        feet = pts[:, [JOINT_INDEX[n] for n in FOOT_JOINTS]].reshape(-1, 3)
        low = feet[feet[:, 1] <= np.quantile(feet[:, 1], config.FLOOR_LOWEST_FRACTION)]
        origin = low.mean(axis=0) - np.array([0, config.HEEL_ABOVE_FLOOR_M, 0])
        toward = camera_centre(self.rig().cameras[0]) - origin
        z = _unit([toward[0], 0.0, toward[2]])
        y = np.array([0.0, 1.0, 0.0])
        return np.array([np.cross(y, z), y, z]), origin

    def truth_in_pipeline_frame(self, times=None) -> np.ndarray:
        A, origin = self.pipeline_frame()
        return (self.truth(times) - origin) @ A.T


# ---- comparing results with the truth ------------------------------------------

def rigid_align(moving, fixed):
    """
    Rotation R and translation t minimising |moving @ R.T + t - fixed| over
    the rows where both are finite (Kabsch). Returns (R, t).
    """
    a = np.asarray(moving).reshape(-1, 3)
    b = np.asarray(fixed).reshape(-1, 3)
    ok = np.isfinite(a).all(axis=1) & np.isfinite(b).all(axis=1)
    a, b = a[ok], b[ok]
    ca, cb = a.mean(axis=0), b.mean(axis=0)
    H = (a - ca).T @ (b - cb)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T
    return R, cb - ca @ R.T


def joint_errors(estimate, truth_points) -> np.ndarray:
    """Per joint distance in metres, NaN where either is missing. Same shape minus the last axis."""
    return np.linalg.norm(np.asarray(estimate) - np.asarray(truth_points), axis=-1)


def mpjpe(estimate, truth_points) -> float:
    """Mean per joint position error over the joints present in both, metres."""
    return float(np.nanmean(joint_errors(estimate, truth_points)))


def aligned_mpjpe(estimate, truth_points):
    """MPJPE after the best rigid alignment; returns (mpjpe, rotation_deg, translation)."""
    R, t = rigid_align(estimate, truth_points)
    moved = np.asarray(estimate) @ R.T + t
    angle = np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))
    return mpjpe(moved, truth_points), float(angle), t
