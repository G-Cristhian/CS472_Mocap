"""
stage2_reconstruct/smooth.py: gap filling and the two smoothers on a known
signal. A slow sine with noise is the signal; a good smoother gets closer to
the clean sine than the noisy input was, and does not touch NaN gaps.
"""
import numpy as np
import pytest

from mocap_pipeline import config, metrics
from mocap_pipeline.joints import NUM_JOINTS
from mocap_pipeline.schemas import Pose3D
from mocap_pipeline.stage2_reconstruct import smooth

FPS = 30.0


def noisy_sine(frames=150, hz=1.0, noise_m=0.01, seed=0):
    """(clean, noisy) Pose3D pairs: every joint moves on the same slow sine plus white noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(frames) / FPS
    base = np.stack([np.sin(2 * np.pi * hz * t), np.cos(2 * np.pi * hz * t), 0.1 * t], axis=1)   # (F, 3)
    clean = np.repeat(base[:, None, :], NUM_JOINTS, axis=1)
    noisy = clean + rng.normal(scale=noise_m, size=clean.shape)
    views = np.full(clean.shape[:2], 3)
    return Pose3D(FPS, clean, views), Pose3D(FPS, noisy, views.copy())


def rms_error(pose, clean):
    d = pose.points - clean.points
    return float(np.sqrt(np.nanmean(np.sum(d * d, axis=2))))


@pytest.mark.parametrize("method", smooth.SMOOTHERS)
def test_smoother_removes_noise_and_keeps_the_signal(method):
    clean, noisy = noisy_sine()
    out = smooth.smooth(noisy, method)
    assert out.points.shape == noisy.points.shape
    # white noise at these settings: savgol leaves ~59% of the error and ~77% of the jitter, butterworth ~68% and ~78%
    assert rms_error(out, clean) < 0.8 * rms_error(noisy, clean)
    assert metrics.jitter_mm(out.points) < 0.9 * metrics.jitter_mm(noisy.points)
    assert np.array_equal(out.num_views, noisy.num_views)


@pytest.mark.parametrize("method", smooth.SMOOTHERS)
def test_gaps_do_not_spread_and_short_runs_are_left_alone(method):
    _, noisy = noisy_sine()
    pts = noisy.points.copy()
    pts[40:46, 0] = np.nan                 # a 6-frame hole in joint 0
    pts[100:148, 1] = np.nan               # joint 1 keeps only a 2-frame tail after frame 148
    pose = Pose3D(FPS, pts, noisy.num_views)
    out = smooth.smooth(pose, method)
    assert np.array_equal(np.isnan(out.points), np.isnan(pts))
    assert np.array_equal(out.points[148:, 1], pts[148:, 1])      # too short for either filter


def test_butterworth_is_zero_phase():
    clean, noisy = noisy_sine(noise_m=0.0)
    out = smooth.smooth(noisy, "butterworth")
    lag = int(np.argmax(np.correlate(out.points[:, 0, 0], clean.points[:, 0, 0], mode="full"))) - (len(clean.points) - 1)
    assert lag == 0


def test_butterworth_rejects_a_cutoff_at_or_above_nyquist(monkeypatch):
    _, noisy = noisy_sine()
    monkeypatch.setattr(config, "BUTTER_CUTOFF_HZ", FPS / 2)
    with pytest.raises(ValueError, match="half the frame rate"):
        smooth.smooth(noisy, "butterworth")


def test_unknown_smoother_is_rejected():
    _, noisy = noisy_sine()
    with pytest.raises(ValueError, match="smoother"):
        smooth.smooth(noisy, "kalman")


def test_default_is_config_smoother(monkeypatch):
    _, noisy = noisy_sine()
    monkeypatch.setattr(config, "SMOOTHER", "butterworth")
    a = smooth.smooth(noisy)
    b = smooth.smooth(noisy, "butterworth")
    assert np.allclose(a.points, b.points)


def test_jitter_is_none_for_short_or_empty_input():
    assert metrics.jitter_mm(np.zeros((2, NUM_JOINTS, 3))) is None
    assert metrics.jitter_mm(np.full((5, NUM_JOINTS, 3), np.nan)) is None
