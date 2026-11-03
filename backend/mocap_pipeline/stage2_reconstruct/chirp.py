"""
Stage 2a, chirp option: put every camera on one clock using a played chirp
instead of a clap.

A chirp is a short tone that sweeps from config.CHIRP_F0_HZ to
config.CHIRP_F1_HZ. One speaker (a laptop, or a phone that is not filming)
plays it once every camera is recording. Each video's audio is correlated
with the same sweep, generated here; the best match is where the chirp starts
in that video. Because the whole half second of sweep is matched, not just the
loudest instant, it is found under talking and room noise that would hide a
clap, and the result does not depend on how hard someone claps.

Make the sound file to play on set:

    cd backend
    python -m mocap_pipeline.stage2_reconstruct.chirp --out chirp.wav

Like the clap, sound needs time to travel: a camera 3 m further from the
speaker hears the chirp about 9 ms later. Keep the speaker about the same
distance from every camera (the middle of the capture area works).
"""
from __future__ import annotations

import argparse
import wave

import numpy as np

from .. import config
from .sync import ClapNotFoundError


class ChirpNotFoundError(ClapNotFoundError):
    """No usable chirp. A ClapNotFoundError, so code that handles a missing clap handles this too."""


def chirp_template(rate: float, f0: float = None, f1: float = None,
                   duration_s: float = None, fade_s: float = None) -> np.ndarray:
    """
    The sweep at `rate` samples per second, peak amplitude 1, float64: a linear
    sweep from f0 to f1 Hz over duration_s, with raised-cosine fades of fade_s
    at both ends so the speaker does not click. Defaults are the config values.
    """
    f0 = config.CHIRP_F0_HZ if f0 is None else f0
    f1 = config.CHIRP_F1_HZ if f1 is None else f1
    duration_s = config.CHIRP_DURATION_S if duration_s is None else duration_s
    fade_s = config.CHIRP_FADE_S if fade_s is None else fade_s

    n = int(round(duration_s * rate))
    t = np.arange(n) / rate
    # instantaneous frequency f0 + (f1 - f0) t / T, integrated to a phase
    phase = 2 * np.pi * (f0 * t + 0.5 * (f1 - f0) / duration_s * t ** 2)
    signal = np.sin(phase)

    fade = min(int(round(fade_s * rate)), n // 2)
    if fade > 0:
        ramp = 0.5 - 0.5 * np.cos(np.pi * np.arange(fade) / fade)
        signal[:fade] *= ramp
        signal[n - fade:] *= ramp[::-1]
    return signal


def match_scores(audio: np.ndarray, template: np.ndarray) -> np.ndarray:
    """
    Normalised correlation of the template with every window of the audio:
    score[k] compares audio[k:k + len(template)] with the template, 1.0 for a
    perfect (scaled) copy, around 1/sqrt(len(template)) for unrelated noise.
    Loudness cancels out, so a quiet chirp scores like a loud one.
    """
    from scipy.signal import correlate

    audio = np.asarray(audio, dtype=np.float64)
    m = len(template)
    if len(audio) < m:
        return np.zeros(0)

    dot = correlate(audio, template, mode="valid", method="fft")
    power = np.r_[0.0, np.cumsum(audio ** 2)]
    energy = power[m:] - power[:-m]

    # digital silence (or a window too quiet to mean anything) scores 0, not 0/0
    floor = 1e-12 * m
    norm = np.linalg.norm(template) * np.sqrt(np.maximum(energy, floor))
    scores = np.where(energy > floor, dot / norm, 0.0)
    return np.clip(scores, -1.0, 1.0)


def _subsample_peak(scores: np.ndarray, i: int) -> float:
    """Peak position to a fraction of a sample, by a parabola through the peak and its neighbours."""
    if i <= 0 or i >= len(scores) - 1:
        return float(i)
    a, b, c = scores[i - 1], scores[i], scores[i + 1]
    denom = a - 2 * b + c
    if denom >= 0:
        return float(i)
    return i + 0.5 * (a - c) / denom


def find_chirp_in_audio(audio: np.ndarray, rate: float, name: str, threshold: float = 1.0) -> float:
    """
    Seconds into the audio at which the chirp starts.

    threshold multiplies config.CHIRP_MIN_SCORE (0.5 accepts a match half as
    good), the same way --clap-threshold scales the clap thresholds. Raises
    ChirpNotFoundError when nothing matches well enough, or when two separate
    places match about equally (chirp played twice, two speakers).
    """
    template = chirp_template(rate)
    scores = match_scores(audio, template)
    if len(scores) == 0:
        raise ChirpNotFoundError(f"{name}: audio is shorter than the chirp")

    # a chirp played with the opposite polarity is still the chirp
    strength = np.abs(scores)
    best = int(np.argmax(strength))
    min_score = config.CHIRP_MIN_SCORE * threshold

    if strength[best] < min_score:
        raise ChirpNotFoundError(
            f"{name}: no chirp in the first {len(audio) / rate:.0f} s. The best match is at "
            f"{best / rate:.2f} s with a score of {strength[best]:.2f} (need {min_score:.2f}; other "
            f"sounds rarely score above 0.1). Was the chirp played while this "
            f"camera was recording? If it is faint, rerun with --clap-threshold {threshold / 2:.2g}; "
            f"otherwise give the chirp times with --sync.")

    echo = int(config.CHIRP_ECHO_S * rate)
    others = strength.copy()
    others[max(0, best - echo):best + echo + 1] = 0.0
    second = int(np.argmax(others))
    if others[second] >= config.CHIRP_MAX_SECOND_PEAK * strength[best]:
        first, later = sorted((best, second))
        raise ChirpNotFoundError(
            f"{name}: the chirp is heard twice, at {first / rate:.2f} s and {later / rate:.2f} s "
            f"(scores {strength[first]:.2f} and {strength[later]:.2f}). Play it once per take, from one "
            f"speaker, or give the chirp times with --sync.")

    return _subsample_peak(strength, best) / rate


def write_chirp_wav(path: str, rate: int = 48000, lead_s: float = 0.5, tail_s: float = 0.5,
                    level: float = 0.8) -> None:
    """
    The chirp as a 16-bit mono WAV, with lead_s of silence before it (some
    players clip the first moment) and tail_s after. level is the peak
    amplitude, 0..1; 0.8 leaves headroom so a speaker does not distort.
    """
    sweep = chirp_template(rate) * level
    signal = np.r_[np.zeros(int(lead_s * rate)), sweep, np.zeros(int(tail_s * rate))]
    pcm = np.round(np.clip(signal, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm.tobytes())


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the sync chirp as a WAV file to play on set.")
    parser.add_argument("--out", default="chirp.wav", help="Output file (default: chirp.wav)")
    parser.add_argument("--rate", type=int, default=48000, help="Sample rate in Hz (default: 48000)")
    args = parser.parse_args()
    write_chirp_wav(args.out, args.rate)
    print(f"Wrote {args.out}: {config.CHIRP_F0_HZ:.0f}-{config.CHIRP_F1_HZ:.0f} Hz sweep, "
          f"{config.CHIRP_DURATION_S * 1000:.0f} ms, starting {0.5:.1f} s into the file")


if __name__ == "__main__":
    main()
