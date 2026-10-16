"""
Pre-flight check for recorded videos, meant to run at the venue before the
tripods come down (docs/field-test-protocol.md, section 9):

    cd backend
    python -m mocap_pipeline.check_videos take01/*

For every video: resolution, frame rate, length, audio, iPhone lens metadata
and the clap time. Then the claps are cross-checked between cameras the same
way the pipeline does. Problems are printed as WARNING (worth a retake) or
FAIL (the pipeline cannot use the file). Exit code 1 if anything FAILed.

Nothing here runs the pose detector, so it takes seconds per take.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from . import config
from .stage2_reconstruct import sync
from .stage2_reconstruct.iphone_camera import (FOCAL_35MM_KEY, LENS_KEY, MODEL_KEY, IPhoneMetadataError,
                                               read_metadata)

# frame rates below this get a warning: the protocol asks for 60 or 120
MIN_RECOMMENDED_FPS = 50.0
# videos in one take should be about the same length
MAX_DURATION_SPREAD_S = 5.0


def video_info(path: str) -> dict:
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            return {"ok": False}
        return {
            "ok": True,
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": float(cap.get(cv2.CAP_PROP_FPS)),
            "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        }
    finally:
        cap.release()


def iphone_info(path: str) -> dict | None:
    """Model, lens and 35 mm focal length if the file carries Apple's metadata, else None."""
    try:
        md = read_metadata(path)
    except (IPhoneMetadataError, OSError, Exception):
        return None
    if not md.get(FOCAL_35MM_KEY):
        return None
    return {"model": md.get(MODEL_KEY), "lens": md.get(LENS_KEY), "focal_35mm": md.get(FOCAL_35MM_KEY)}


def clap_time(path: str) -> tuple[float | None, str | None]:
    """Clap time in seconds, or (None, reason)."""
    try:
        audio = sync._read_audio(path, config.CLAP_SEARCH_WINDOW_S)
        return sync._clap_from_loudness(sync._loudness(audio), path), None
    except sync.ClapNotFoundError as e:
        return None, str(e)


def check(video_paths: list[str]) -> int:
    problems = 0
    results = []

    for path in video_paths:
        name = Path(path).name
        print(f"\n{name}")
        info = video_info(path)
        if not info["ok"]:
            print("  FAIL    cannot be opened as a video")
            problems += 1
            results.append(None)
            continue

        duration = info["frames"] / info["fps"] if info["fps"] else 0.0
        print(f"  video   {info['width']}x{info['height']}, {info['fps']:.2f} fps, "
              f"{info['frames']} frames, {duration:.1f} s")
        if info["fps"] and info["fps"] < MIN_RECOMMENDED_FPS:
            print(f"  WARNING frame rate under {MIN_RECOMMENDED_FPS:.0f}; the protocol asks for 60 (or 120 for set C)")

        apple = iphone_info(path)
        is_mov = Path(path).suffix.lower() == ".mov"
        if apple:
            print(f"  lens    {apple['model']}, {apple['lens']}, {apple['focal_35mm']} mm (35 mm equiv.) from metadata")
        elif is_mov:
            print("  WARNING .MOV without iPhone lens metadata: re-exported? Copy the original again, "
                  "or run with --camera webcam --fov")
        else:
            print(f"  lens    no lens metadata (not an iPhone file): needs --fov, default {config.DEFAULT_HFOV_DEG:.0f}")

        t, reason = clap_time(path)
        if t is None:
            print(f"  FAIL    no clap: {reason}")
            problems += 1
        else:
            print(f"  clap    {t:.3f} s")
            if t > config.CLAP_SEARCH_WINDOW_S - 1.0:
                print(f"  WARNING clap close to the {config.CLAP_SEARCH_WINDOW_S:.0f} s search window; clap sooner")

        results.append({**info, "duration": duration, "clap": t})

    good = [r for r in results if r]
    if len(good) >= 2:
        print("\nacross cameras")
        fps = {round(r["fps"]) for r in good}
        if len(fps) > 1:
            print(f"  WARNING frame rates differ between phones: {sorted(fps)} (fine for the pipeline, "
                  f"but a take set should be recorded at one rate)")
        sizes = {(r["width"], r["height"]) for r in good}
        if len(sizes) > 1:
            print(f"  WARNING resolutions differ between phones: {sorted(sizes)}")
        durations = [r["duration"] for r in good]
        if max(durations) - min(durations) > MAX_DURATION_SPREAD_S:
            print(f"  WARNING lengths differ by {max(durations) - min(durations):.1f} s; "
                  f"was a phone started late or stopped early?")
        if all(r["clap"] is not None for r in good) and len(good) == len(results):
            try:
                refined = sync.detect_claps(video_paths)
                print("  claps   " + ", ".join(f"{Path(p).name} {t:.3f} s" for p, t in zip(video_paths, refined))
                      + " (cross-checked against camera 0)")
            except sync.ClapNotFoundError as e:
                print(f"  WARNING cross-check failed: {e}")
    elif len(video_paths) < 2:
        print("\nWARNING one video given; the pipeline needs at least 2")

    print("\n" + ("All files usable." if problems == 0 else f"{problems} file(s) the pipeline cannot use."))
    return 1 if problems else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check recorded videos before leaving the venue.")
    parser.add_argument("videos", nargs="+", help="The videos of one take, camera 0 first.")
    args = parser.parse_args()
    sys.exit(check(args.videos))


if __name__ == "__main__":
    main()
