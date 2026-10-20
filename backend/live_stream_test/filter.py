"""
One Euro Filter for real-time 3D landmark jitter reduction without lag.
Reference: Casiez et al. 2012 (1 € Filter).
"""
import math
from typing import Dict, List, Optional, Tuple, Any


class LowPassFilter:
    def __init__(self, alpha: float = 0.5):
        self._alpha = alpha
        self._last_val: Optional[float] = None

    def set_alpha(self, alpha: float):
        self._alpha = max(0.0, min(1.0, alpha))

    def filter(self, value: float) -> float:
        if self._last_val is None:
            self._last_val = value
        else:
            self._last_val = self._alpha * value + (1.0 - self._alpha) * self._last_val
        return self._last_val

    def last_value(self) -> Optional[float]:
        return self._last_val

    def reset(self):
        self._last_val = None


class OneEuroFilter:
    """
    1-Euro filter for a single float scalar.
    Dynamically adjusts smoothing alpha based on derivative (velocity).
    """
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_filt = LowPassFilter()
        self.dx_filt = LowPassFilter()
        self.last_time: Optional[float] = None

    def _alpha(self, rate: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te = 1.0 / rate
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float, timestamp_s: float) -> float:
        if self.last_time is None:
            self.last_time = timestamp_s
            return self.x_filt.filter(x)

        dt = timestamp_s - self.last_time
        self.last_time = timestamp_s

        if dt <= 0:
            return self.x_filt.last_value() or x

        rate = 1.0 / dt
        prev_x = self.x_filt.last_value()
        dx = 0.0 if prev_x is None else (x - prev_x) * rate

        edx = self.dx_filt.filter(dx)
        self.dx_filt.set_alpha(self._alpha(rate, self.d_cutoff))

        cutoff = self.min_cutoff + self.beta * abs(edx)
        self.x_filt.set_alpha(self._alpha(rate, cutoff))

        return self.x_filt.filter(x)

    def reset(self):
        self.x_filt.reset()
        self.dx_filt.reset()
        self.last_time = None


class JointFilter3D:
    """
    Applies independent 1-Euro filters to (x, y, z) coordinates of a 3D joint.
    """
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007):
        self.filter_x = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.filter_y = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.filter_z = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)

    def filter(self, x: float, y: float, z: float, timestamp_s: float) -> Tuple[float, float, float]:
        fx = self.filter_x.filter(x, timestamp_s)
        fy = self.filter_y.filter(y, timestamp_s)
        fz = self.filter_z.filter(z, timestamp_s)
        return fx, fy, fz

    def reset(self):
        self.filter_x.reset()
        self.filter_y.reset()
        self.filter_z.reset()


class PoseFilter:
    """
    Maintains a set of 3D joint filters for all MediaPipe joints.
    """
    def __init__(self, min_cutoff: float = 1.2, beta: float = 0.01):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.filters: Dict[int, JointFilter3D] = {}

    def filter_pose(self, landmarks_3d: List[Dict[str, Any]], timestamp_s: float) -> List[Dict[str, Any]]:
        """
        Takes a list of 33 landmark dicts {'x': ..., 'y': ..., 'z': ..., 'visibility': ...}
        and returns smoothed coordinates.
        """
        smoothed = []
        for idx, lm in enumerate(landmarks_3d):
            if idx not in self.filters:
                self.filters[idx] = JointFilter3D(min_cutoff=self.min_cutoff, beta=self.beta)

            x = lm.get('x', 0.0)
            y = lm.get('y', 0.0)
            z = lm.get('z', 0.0)
            vis = lm.get('visibility', 1.0)

            # If visibility is low, keep unfiltered or decay
            if vis is not None and vis < 0.2:
                smoothed.append(lm)
                continue

            sx, sy, sz = self.filters[idx].filter(x, y, z, timestamp_s)
            smoothed.append({
                'x': sx,
                'y': sy,
                'z': sz,
                'visibility': vis
            })
        return smoothed

    def reset(self):
        for f in self.filters.values():
            f.reset()
