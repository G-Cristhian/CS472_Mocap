"""
Synthetic "phone videos" for tests that need real files but no footage: a
moving rectangle on a grey background, plus an audio track with room noise and
one sharp clap at a chosen time. Each camera gets a different clap time, as if
the phones had been started at different moments.

MediaPipe finds no person in these (every joint is NaN), so they exercise
decoding, the clap search, resampling and the file handling, not the geometry.
"""
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

AUDIO_RATE = 48000


def write_video(path, fps, seconds, clap_at, width=640, height=360, seed=0, clap_gain=1.0):
    """clap_gain scales the clap against the room noise (1.0 is a loud clap, 0.02 a faint one)."""
    rng = np.random.default_rng(seed)
    with av.open(str(path), "w") as out:
        v = out.add_stream("mpeg4", rate=fps)
        v.width, v.height, v.pix_fmt = width, height, "yuv420p"
        a = out.add_stream("aac", rate=AUDIO_RATE)
        a.layout = "mono"

        n_frames = int(seconds * fps)
        for i in range(n_frames):
            img = np.full((height, width, 3), 120, np.uint8)
            x = int((i / n_frames) * (width - 60))
            img[100:260, x:x + 60] = (30, 30, 200)
            frame = av.VideoFrame.from_ndarray(img, format="rgb24")
            frame.pts = i
            frame.time_base = Fraction(1, fps)
            for pkt in v.encode(frame):
                out.mux(pkt)
        for pkt in v.encode():
            out.mux(pkt)

        audio = rng.normal(0, 0.003, int(seconds * AUDIO_RATE)).astype(np.float32)  # room noise
        if clap_at is not None:
            s = int(clap_at * AUDIO_RATE)
            burst = rng.normal(0, 0.8 * clap_gain, int(0.015 * AUDIO_RATE)).astype(np.float32)
            burst *= np.exp(-np.linspace(0, 6, len(burst)))           # sharp attack, fast decay
            audio[s:s + len(burst)] += burst
        chunk = 1024
        pts = 0
        for start in range(0, len(audio), chunk):
            block = audio[start:start + chunk]
            frame = av.AudioFrame.from_ndarray(block.reshape(1, -1), format="flt", layout="mono")
            frame.sample_rate = AUDIO_RATE
            frame.pts = pts
            frame.time_base = Fraction(1, AUDIO_RATE)
            pts += len(block)
            for pkt in a.encode(frame):
                out.mux(pkt)
        for pkt in a.encode():
            out.mux(pkt)
