"""
Pre-flight check for recorded videos, meant to run at the venue before the
tripods come down (docs/procedures/filming.md, section 9):

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
from .stage2_reconstruct.iphone_camera import (CINEMATIC_INTENT_KEY, CINEMATIC_KEY, LENS_KEY, MAKE_KEY, MODEL_KEY,
                                               SOFTWARE_KEY, focal_35mm, read_metadata)

# frame rates below this get a warning: the protocol asks for 60 or 120
MIN_RECOMMENDED_FPS = 50.0
# videos in one take should be about the same length
MAX_DURATION_SPREAD_S = 5.0
# 35 mm equivalent focal lengths of the 1x lens. Apple's tech specs (support.apple.com/121032, /125089,
# /125090) list the main camera at 24 mm (16 Pro Max, 17 Pro) or 26 mm (17), the 0.5x ultra wide at 13 mm
# and 2x and telephoto at 48 mm and up. Video files checked: a 16 Pro Max whose lens_model names its
# 6.765mm f/1.78 main lens read 25; a 17, 17 Pro Max and 18 Pro naming a 2.22mm f/2.2 lens (the
# ultra wide's aperture in the specs) read 14. The 18 Pro's specs were not checked
MAIN_LENS_35MM = (20.0, 35.0)


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
    """Apple's tags from the file (make, model, iOS version, lens, 35 mm focal length, Cinematic mode), None if unreadable."""
    try:
        md = read_metadata(path)
    except Exception:
        return None
    return {"apple": md.get(MAKE_KEY) == "Apple", "model": md.get(MODEL_KEY), "software": md.get(SOFTWARE_KEY),
            "lens": md.get(LENS_KEY), "focal_35mm": focal_35mm(md),
            "cinematic": CINEMATIC_KEY in md or md.get(CINEMATIC_INTENT_KEY) == 1}


def lens_report(path: str) -> list[str]:
    """The lens lines check() prints for one video."""
    apple = iphone_info(path) or {}
    focal = apple.get("focal_35mm")
    lines = []
    if focal:
        lines.append(f"  lens    {apple['model']}, {apple['lens']}, {focal:g} mm (35 mm equiv.) from metadata")
        if focal < MAIN_LENS_35MM[0]:
            lines.append("  WARNING that is the 0.5x ultra wide lens; the protocol asks for 1x")
        elif focal > MAIN_LENS_35MM[1]:
            lines.append("  WARNING that is a telephoto lens or zoomed in; the protocol asks for 1x")
    elif apple.get("apple"):
        lines.append(f"  WARNING {apple['model']} (iOS {apple['software']}) file without a focal length in its metadata: "
                     f"the pipeline will use --fov, default {config.DEFAULT_HFOV_DEG:.0f}; pass the measured value")
    elif Path(path).suffix.lower() == ".mov":
        lines.append("  WARNING .MOV without iPhone lens metadata: re-exported? Copy the original again, "
                     "or run with --camera webcam --fov")
    else:
        lines.append(f"  lens    no lens metadata (not an iPhone file): needs --fov, default {config.DEFAULT_HFOV_DEG:.0f}")
    if apple.get("cinematic"):
        # untested beyond one file: an iPhone 18 Pro Cinematic recording was reported to calibrate from
        # the performer at 733 to 855 px (not rerun here), against 713 px from its lens metadata
        lines.append("  WARNING recorded in Cinematic mode: untested with the pipeline, and its framing may not "
                     "match the lens metadata; record in Video mode")
    return lines


def clap_time(path: str, threshold: float = 1.0) -> tuple[float | None, str | None]:
    """Clap time in seconds, or (None, reason). threshold as in sync.find_clap_time."""
    try:
        audio = sync._read_audio(path, config.CLAP_SEARCH_WINDOW_S)
        return sync._clap_from_loudness(sync._loudness(audio), path, threshold), None
    except sync.ClapNotFoundError as e:
        return None, str(e)


def check(video_paths: list[str], threshold: float = 1.0) -> int:
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

        for line in lens_report(path):
            print(line)

        t, reason = clap_time(path, threshold)
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
                refined = sync.detect_claps(video_paths, threshold)
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
    parser.add_argument("--clap-threshold", type=float, default=1.0,
                        help="Multiplies how loud a clap must be against the room (0.5 accepts a clap half as strong).")
    args = parser.parse_args()
    sys.exit(check(args.videos, args.clap_threshold))


if __name__ == "__main__":
    main()
