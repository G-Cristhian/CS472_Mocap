"""
Search for a good layout with simulated annealing (paper section 3.5).

Cameras stand on tripods inside a rectangle of floor around the capture area
(Constraints) and are aimed at one point, the middle of the performer. The
annealer moves one camera at a time and keeps the layout with the lowest
metric.layout_cost it ever saw.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import config
from ..schemas import Camera, CameraRig
from .metric import layout_cost


@dataclass(frozen=True)
class Constraints:
    """
    Where phones may stand. Metres, in the pipeline's world frame (Y up, floor
    at Y = 0, +Z toward the performer's front). Every camera is aimed at `aim`.
    """
    x_range: tuple = (-4.0, 4.0)
    z_range: tuple = (-4.0, 4.0)
    height_range: tuple = (0.8, 1.8)        # tripod heights
    min_distance_m: float = 1.5             # floor distance from the aim point: no phone inside the capture area
    aim: tuple = (0.0, 0.9, 0.0)            # roughly hip height of a standing performer
    width: int = 1920
    height: int = 1080
    hfov_deg: float = config.DEFAULT_HFOV_DEG


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def intrinsics(constraints: Constraints) -> np.ndarray:
    f = (constraints.width / 2.0) / np.tan(np.radians(constraints.hfov_deg) / 2.0)
    return np.array([[f, 0, constraints.width / 2.0], [0, f, constraints.height / 2.0], [0, 0, 1.0]])


def look_at(camera_id: str, position, aim, K) -> Camera:
    """A camera at `position` looking at `aim`, image x to the right, y down (OpenCV convention)."""
    position = np.asarray(position, dtype=float)
    forward = _unit(np.asarray(aim, dtype=float) - position)
    right = _unit(np.cross(forward, [0.0, 1.0, 0.0]))
    down = np.cross(forward, right)
    R = np.array([right, down, forward])
    return Camera(camera_id=camera_id, K=np.asarray(K, dtype=float), R=R, t=-R @ position)


def rig_from_positions(positions, constraints: Constraints) -> CameraRig:
    K = intrinsics(constraints)
    cameras = [look_at(f"cam{i}", p, constraints.aim, K) for i, p in enumerate(np.asarray(positions, dtype=float))]
    return CameraRig(cameras=cameras, reprojection_error_px={c.camera_id: 0.0 for c in cameras}, is_metric=True)


def _random_position(constraints: Constraints, rng: np.random.Generator) -> np.ndarray:
    aim = np.asarray(constraints.aim, dtype=float)
    for _ in range(1000):
        p = np.array([rng.uniform(*constraints.x_range), rng.uniform(*constraints.height_range),
                      rng.uniform(*constraints.z_range)])
        if np.hypot(p[0] - aim[0], p[2] - aim[2]) >= constraints.min_distance_m:
            return p
    raise ValueError("the constraints leave no room for a camera outside min_distance_m")


def _clip(p, constraints: Constraints) -> np.ndarray:
    return np.array([np.clip(p[0], *constraints.x_range), np.clip(p[1], *constraints.height_range),
                     np.clip(p[2], *constraints.z_range)])


def random_layout(num_cameras: int, constraints: Constraints = Constraints(),
                  rng: np.random.Generator | None = None) -> CameraRig:
    """Each camera at a random allowed position, aimed at the centre of the capture volume."""
    rng = rng if rng is not None else np.random.default_rng(0)
    return rig_from_positions([_random_position(constraints, rng) for _ in range(num_cameras)], constraints)


def optimise_layout(num_cameras: int, constraints: Constraints, target_points,
                    iterations: int = 2000, seed: int = 0, step_m: float = 0.5,
                    initial: CameraRig | None = None) -> CameraRig:
    """
      1. Start from random_layout (or `initial`); cost = metric.layout_cost.
      2. Each step: move ONE random camera by a Gaussian step within the constraints
         (cameras always aim at constraints.aim, so a move is also a re-aim).
      3. Accept if better. If worse, accept with probability
         exp(-(new - old) / temperature); the temperature falls linearly to zero.
      4. Keep and return the best layout seen.
    The uncovered-point penalty in metric.point_error matters here: without
    it all cameras cluster on one spot (paper section 3.5).

    iterations=2000 with a few hundred target points takes tens of seconds in
    pure Python; the paper's 20000 is for the final answer, not for trying ideas.
    """
    rng = np.random.default_rng(seed)
    targets = np.asarray(target_points, dtype=float).reshape(-1, 3)
    if initial is not None:
        from .metric import camera_centre
        positions = np.array([camera_centre(c) for c in initial.cameras])
    else:
        positions = np.array([_random_position(constraints, rng) for _ in range(num_cameras)])

    cost = layout_cost(rig_from_positions(positions, constraints), targets)
    best_positions, best_cost = positions.copy(), cost
    temperature0 = max(cost, 1.0) * 0.05
    aim = np.asarray(constraints.aim, dtype=float)

    for k in range(iterations):
        temperature = temperature0 * (1.0 - k / iterations) + 1e-9
        i = int(rng.integers(num_cameras))
        candidate = positions.copy()
        candidate[i] = _clip(positions[i] + rng.normal(0.0, step_m, 3), constraints)
        if np.hypot(candidate[i][0] - aim[0], candidate[i][2] - aim[2]) < constraints.min_distance_m:
            continue
        new_cost = layout_cost(rig_from_positions(candidate, constraints), targets)
        if new_cost <= cost or rng.random() < np.exp(-(new_cost - cost) / temperature):
            positions, cost = candidate, new_cost
            if cost < best_cost:
                best_positions, best_cost = positions.copy(), cost

    return rig_from_positions(best_positions, constraints)
