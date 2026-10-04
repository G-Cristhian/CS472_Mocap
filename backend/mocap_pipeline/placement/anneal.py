"""
Search for a good layout with simulated annealing (paper section 3.5).
"""
from __future__ import annotations

from ..schemas import CameraRig


def random_layout(num_cameras: int, constraints) -> CameraRig:
    """
    TODO: place each camera at a random allowed position, aimed at the centre
    of the capture volume. `constraints` describes where phones may stand
    (room size, tripod height range); define that structure here.
    """
    raise NotImplementedError


def optimise_layout(num_cameras: int, constraints, target_points,
                    iterations: int = 20000) -> CameraRig:
    """
    TODO:
      1. Start from random_layout; cost = metric.layout_cost.
      2. Each step: move or re-aim ONE random camera within the constraints.
      3. Accept if better. If worse, accept with probability
         exp(-(new - old) / temperature); lower the temperature each step.
      4. Keep and return the best layout seen.
    The uncovered-point penalty in metric.point_error matters here: without
    it all cameras cluster on one spot (paper section 3.5).
    """
    raise NotImplementedError
