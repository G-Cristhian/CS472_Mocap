"""
Stage 2a: put every camera on one clock using the clap.

Input : the video paths and their Keypoints2D.
Output: SyncResult, plus Keypoints2D resampled onto the shared timeline.

The clap is found in each video's audio track. Audio is decoded with PyAV
(pip package "av", which bundles its own ffmpeg, so no system ffmpeg is
needed). If a video has no audio or no clear clap, give the clap times by
hand (run_pipeline.py --sync).
"""
from __future__ import annotations

import numpy as np

from .. import config
from ..schemas import Keypoints2D, SyncResult


class ClapNotFoundError(Exception):
    pass


def _read_audio(video_path: str, max_seconds: float) -> np.ndarray:
    """First max_seconds of the video's audio, mono float32 at config.CLAP_AUDIO_RATE."""
    import av

    try:
        container = av.open(str(video_path))
    except av.error.FFmpegError as e:
        raise ClapNotFoundError(f"{video_path}: could not open ({e})")

    with container:
        if not container.streams.audio:
            raise ClapNotFoundError(f"{video_path} has no audio track")
        
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="flt", layout="mono", rate=config.CLAP_AUDIO_RATE)
        max_samples = int(max_seconds * config.CLAP_AUDIO_RATE)

        chunks, n = [], 0

        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunk = out.to_ndarray().reshape(-1)
                chunks.append(chunk)
                n += len(chunk)
            if n >= max_samples:
                break

    if not chunks:
        raise ClapNotFoundError(f"{video_path}: audio track is empty")
    
    return np.concatenate(chunks)[:max_samples]


def _loudness(audio: np.ndarray) -> np.ndarray:
    """
    Root-mean-square loudness every config.CLAP_WINDOW_S seconds, averaged over
    config.CLAP_SMOOTH_S (centred) so the pitch of a voice doesn't make speech
    flicker like a string of tiny claps. The centring shifts every camera's
    clap by the same amount, so the offsets between cameras are unaffected.
    """
    hop = max(1, int(config.CLAP_WINDOW_S * config.CLAP_AUDIO_RATE))
    span = max(hop, int(config.CLAP_SMOOTH_S * config.CLAP_AUDIO_RATE))

    power = np.r_[0.0, np.cumsum(audio.astype(np.float64) ** 2)]
    centres = np.arange(0, len(audio), hop)

    lo = np.clip(centres - span // 2, 0, len(audio))
    hi = np.clip(centres + span // 2, 0, len(audio))

    return np.sqrt((power[hi] - power[lo]) / np.maximum(hi - lo, 1))


def _clap_from_loudness(rms: np.ndarray, name: str) -> float:
    """
    Seconds of the clap onset: the sharpest loud transient. A clap goes from
    background to full loudness within a few milliseconds; speech, music and
    footsteps ramp up much more slowly, so the test is how much louder a
    moment is than 30-100 ms before it (config.CLAP_MIN_RISE), among moments
    that stand out from the background (config.CLAP_MIN_PROMINENCE). The gap
    of 30 ms skips the codec's pre-echo: AAC audio (what phones record)
    smears a clap's energy up to ~20 ms earlier.
    """
    win_s = config.CLAP_WINDOW_S
    near, far = max(1, int(0.03 / win_s)), max(2, int(0.10 / win_s))

    if len(rms) < 2 * far:
        raise ClapNotFoundError(f"{name}: audio too short to find a clap")

    noise = np.median(rms) + 1e-9

    # loudest moment 30-100 ms before each window
    padded = np.r_[np.full(far, rms[0]), rms]
    before = np.max(np.lib.stride_tricks.sliding_window_view(padded, far - near)[:len(rms)], axis=1)
    rise = rms / (before + noise)
    rise[rms < config.CLAP_MIN_PROMINENCE * noise] = 0

    # strongest candidates first; a clap must also reach its peak quickly (speech ramps up over ~50-100 ms)
    ten_ms = max(1, int(0.01 / win_s))
    best = 0.0

    for i in np.argsort(rise)[::-1][:200]:
        if rise[i] < config.CLAP_MIN_RISE:
            break

        # the sound's real peak: a clap peaks within a few ms, speech keeps getting louder for longer
        top_at = i + int(np.argmax(rms[i:i + far + 1]))
        top = rms[top_at]

        # rise time: back from the peak to where it was a quarter of the way up from what came before
        # (measured above that level, so a clap on top of talking still counts)
        quarter = before[i] + 0.25 * (top - before[i])
        j = top_at

        while j > 0 and rms[j - 1] >= quarter and top_at - j < far:
            j -= 1
        if (top_at - j) * win_s > config.CLAP_MAX_RISE_S:
            best = max(best, rise[i])
            continue

        # onset: first window within 10 ms before the peak that is half of the way up
        start = max(0, top_at - ten_ms)
        onset = start + int(np.argmax(rms[start:top_at + 1] >= before[i] + 0.5 * (top - before[i])))

        return onset * win_s

    raise ClapNotFoundError(
        f"{name}: no clear clap in the first {config.CLAP_SEARCH_WINDOW_S:.0f} s "
        f"(no sound rose sharply enough: need {config.CLAP_MIN_RISE:.0f}x louder than 30-100 ms before, "
        f"reaching its peak within {config.CLAP_MAX_RISE_S * 1000:.0f} ms)")


def find_clap_time(video_path: str) -> float:
    """
    Seconds into this video at which the clap occurs.

    Looks only at the first config.CLAP_SEARCH_WINDOW_S seconds of audio and
    takes the sharpest loud transient. Raises ClapNotFoundError if there is no
    obvious peak, so the user re-records (or gives --sync) instead of getting
    silently wrong 3D.
    """
    audio = _read_audio(video_path, config.CLAP_SEARCH_WINDOW_S)
    return _clap_from_loudness(_loudness(audio), str(video_path))


def _refine_against_reference(rms_ref, clap_ref, rms, clap, name):
    """
    Cross-check one camera's clap against camera 0's: correlate the loudness
    around both claps and shift this camera's clap by the best lag.
    """
    win_s = config.CLAP_WINDOW_S
    half = int(config.CLAP_REFINE_WINDOW_S / win_s)
    i_ref, i = int(round(clap_ref / win_s)), int(round(clap / win_s))

    if i_ref - half < 0 or i - half < 0 or i_ref + half > len(rms_ref) or i + half > len(rms):
        return clap
    
    a = rms_ref[i_ref - half:i_ref + half]
    b = rms[i - half:i + half]
    a, b = a - a.mean(), b - b.mean()

    if not a.any() or not b.any():
        return clap

    corr = np.correlate(b, a, mode="full")
    shift = (int(np.argmax(corr)) - (len(a) - 1)) * win_s

    if abs(shift) > config.CLAP_MAX_REFINE_S:
        print(f"warning: {name}: clap cross-check against camera 0 disagrees by {shift * 1000:.0f} ms, "
              f"keeping the detected clap (check it, or give --sync)")
        return clap
    
    return clap + shift


def detect_claps(video_paths: list[str]) -> list[float]:
    """Clap time of every video, each cross-checked against camera 0's."""
    loudness = [_loudness(_read_audio(v, config.CLAP_SEARCH_WINDOW_S)) for v in video_paths]
    claps = [_clap_from_loudness(rms, str(v)) for rms, v in zip(loudness, video_paths)]

    return [claps[0]] + [
        _refine_against_reference(loudness[0], claps[0], loudness[c], claps[c], str(video_paths[c]))
        for c in range(1, len(claps))]


def _resample(kp: Keypoints2D, times: np.ndarray, common: np.ndarray):
    """Linear interpolation of points and confidence onto the common timeline."""
    n = len(times)
    idx = np.clip(np.searchsorted(times, common, side="right"), 1, n - 1)
    t0, t1 = times[idx - 1], times[idx]
    inside = (common >= t0) & (common <= t1)

    # never bridge a hole longer than a couple of this camera's frames
    inside &= (t1 - t0) <= config.SYNC_MAX_INTERP_GAP_FRAMES / kp.fps
    w = np.where(t1 > t0, (common - t0) / np.where(t1 > t0, t1 - t0, 1.0), 0.0)

    # if either neighbour is NaN the result is NaN (NaN propagates through the sum)
    points = (1 - w)[:, None, None] * kp.points[idx - 1] + w[:, None, None] * kp.points[idx]
    confidence = (1 - w)[:, None] * kp.confidence[idx - 1] + w[:, None] * kp.confidence[idx]
    points[~inside] = np.nan
    confidence[~inside] = 0.0
    confidence[np.isnan(points).any(axis=2)] = 0.0

    return points, confidence


def synchronise(video_paths: list[str],
                keypoints: list[Keypoints2D],
                clap_times: list[float] | None = None) -> tuple[SyncResult, list[Keypoints2D]]:
    """
    1. Clap time per video: given by hand (clap_times) or detect_claps.
    2. Shift each camera's timestamps so the clap is t = 0.
    3. Shared timeline from 0 to the earliest end time among cameras, at
       config.TARGET_FPS.
    4. Resample every camera's points and confidence onto that timeline by
       linear interpolation between its two nearest frames. If either
       neighbour is NaN the result is NaN.
    After this, frame i means the same instant in every camera.
    """
    if clap_times is None:
        clap_times = detect_claps(video_paths)

    shifted = [kp.timestamps - clap for kp, clap in zip(keypoints, clap_times)]
    end = min(t[-1] for t in shifted)

    if end <= 0:
        raise ValueError("a video ends before its clap, check the clap times")
    
    common = np.arange(0.0, end + 1e-9, 1.0 / config.TARGET_FPS)

    resampled = []

    for kp, times in zip(keypoints, shifted):
        points, confidence = _resample(kp, times, common)
        resampled.append(Keypoints2D(
            camera_id=kp.camera_id, video_path=kp.video_path, width=kp.width, height=kp.height,
            fps=config.TARGET_FPS, timestamps=common, points=points, confidence=confidence))

    sync = SyncResult(
        clap_time_s={kp.camera_id: float(c) for kp, c in zip(keypoints, clap_times)},
        common_timestamps=common)
    
    return sync, resampled
