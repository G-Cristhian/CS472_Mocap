"""
iPhone lens metadata on files built box by box (tests/apple_metadata.py), laid
out like originals from iOS 26.6.2 and 27.0: the lens keys in the video
track's 'meta' atom, make and model in the movie's.
"""
import numpy as np
import pytest

from mocap_pipeline import check_videos
from mocap_pipeline.stage2_reconstruct import iphone_camera as ic
from tests.apple_metadata import add_apple_metadata, trak_box, write_mov
from tests.synthetic_video import write_video

MOVIE = {ic.MAKE_KEY: "Apple", ic.MODEL_KEY: "iPhone 17 Pro Max", ic.SOFTWARE_KEY: "26.6.2"}
MAIN = {ic.LENS_KEY: "iPhone 17 Pro Max back camera 6.765mm f/1.78", ic.FOCAL_35MM_KEY: "25"}
ULTRA_WIDE = {ic.LENS_KEY: "iPhone 17 Pro Max back camera 2.22mm f/2.2", ic.FOCAL_35MM_KEY: "14"}


def iphone_file(tmp_path, video=MAIN, movie=MOVIE, name="IMG_0001.MOV", tracks_before=()):
    path = tmp_path / name
    write_mov(path, movie, [*tracks_before, trak_box(b"vide", video), trak_box(b"soun")])
    return str(path)


def test_lens_keys_are_read_from_the_video_track(tmp_path):
    md = ic.read_metadata(iphone_file(tmp_path))
    assert md[ic.MODEL_KEY] == "iPhone 17 Pro Max"
    assert md[ic.LENS_KEY] == "iPhone 17 Pro Max back camera 6.765mm f/1.78"
    assert ic.focal_35mm(md) == 25.0


def test_track_level_focal_length_makes_an_iphone_camera(tmp_path):
    path = iphone_file(tmp_path)
    assert ic.is_iphone_video(path)
    K, _ = ic.iphone_intrinsics(path, (1920, 1080))
    assert K[0, 0] == pytest.approx(25 * np.hypot(1920, 1080) / ic.FULL_FRAME_DIAGONAL_MM)   # about 1273 px
    assert (K[0, 2], K[1, 2]) == (960, 540)


def test_movie_level_keys_still_work_and_win(tmp_path):
    path = tmp_path / "old.MOV"
    write_mov(path, {**MOVIE, ic.FOCAL_35MM_KEY: "26"}, [trak_box(b"vide", ULTRA_WIDE)])
    md = ic.read_metadata(str(path))
    assert ic.focal_35mm(md) == 26.0                 # the movie's value is kept
    assert md[ic.LENS_KEY] == ULTRA_WIDE[ic.LENS_KEY]  # the track fills in what the movie lacks


def test_only_the_video_track_is_read(tmp_path):
    decoy = trak_box(b"meta", {ic.FOCAL_35MM_KEY: "77"})     # a timed metadata track listed first
    path = iphone_file(tmp_path, tracks_before=[decoy])
    assert ic.focal_35mm(ic.read_metadata(path)) == 25.0


@pytest.mark.parametrize("value, expected", [("25", 25.0), ("50.00mm", 50.0), (" 13.5 mm", 13.5), (26, 26.0),
                                             ("", None), ("unknown", None), (0, None), (b"\x19", None)])
def test_focal_length_text_forms(value, expected):
    # Apple's docs give "50.00mm" as the example; the files checked have "25" or "14"
    assert ic.focal_35mm({ic.FOCAL_35MM_KEY: value}) == expected


def test_apple_file_without_lens_keys_is_not_called_re_exported(tmp_path):
    path = tmp_path / "IMG_0002.MOV"
    write_mov(path, MOVIE, [trak_box(b"vide")])
    assert not ic.is_iphone_video(str(path))
    with pytest.raises(ic.IPhoneMetadataError) as info:
        ic.iphone_intrinsics(str(path), (1920, 1080))
    assert "re-exported" not in str(info.value)
    assert "iPhone 17 Pro Max, iOS 26.6.2" in str(info.value)

    lines = "\n".join(check_videos.lens_report(str(path)))
    assert "re-exported" not in lines
    assert "WARNING iPhone 17 Pro Max (iOS 26.6.2) file without a focal length" in lines
    assert "--fov, default 65" in lines


def test_mov_without_apple_tags_is_still_called_re_exported(tmp_path):
    path = tmp_path / "shared.mov"
    write_mov(path, None, [trak_box(b"vide")])
    assert check_videos.lens_report(str(path)) == [
        "  WARNING .MOV without iPhone lens metadata: re-exported? Copy the original again, "
        "or run with --camera webcam --fov"]


def test_main_lens_reports_without_warnings(tmp_path):
    assert check_videos.lens_report(iphone_file(tmp_path)) == [
        "  lens    iPhone 17 Pro Max, iPhone 17 Pro Max back camera 6.765mm f/1.78, 25 mm (35 mm equiv.) from metadata"]


@pytest.mark.parametrize("focal, warning", [("14", "0.5x ultra wide"), ("77", "telephoto")])
def test_lenses_other_than_1x_are_warned(tmp_path, focal, warning):
    lines = check_videos.lens_report(iphone_file(tmp_path, {**MAIN, ic.FOCAL_35MM_KEY: focal}))
    assert lines[0].startswith("  lens    ") and f"{focal} mm (35 mm equiv.)" in lines[0]
    assert lines[1].startswith("  WARNING") and warning in lines[1] and "protocol asks for 1x" in lines[1]


@pytest.mark.parametrize("cinematic", [
    {ic.CINEMATIC_KEY: b"\0\0\0\x08cvid", ic.CINEMATIC_INTENT_KEY: 0},    # as on an iPhone 18 Pro, iOS 27.0
    {ic.CINEMATIC_INTENT_KEY: 1},                                           # Apple's documented flag
])
def test_cinematic_mode_is_warned(tmp_path, cinematic):
    lines = check_videos.lens_report(iphone_file(tmp_path, movie={**MOVIE, **cinematic}))
    assert any(line.startswith("  WARNING Cinematic mode keys") for line in lines)


def test_not_cinematic_without_the_keys(tmp_path):
    lines = check_videos.lens_report(iphone_file(tmp_path, movie={**MOVIE, ic.CINEMATIC_INTENT_KEY: 0}))
    assert not any("Cinematic" in line for line in lines)


def test_check_reads_the_lens_from_a_real_video(tmp_path, capsys):
    """Apple's boxes written into a decodable video: check() prints the lens and the 0.5x warning."""
    phone = tmp_path / "IMG_0003.MOV"
    write_video(phone, fps=60, seconds=3.0, clap_at=1.0, seed=4)
    add_apple_metadata(phone, MOVIE, ULTRA_WIDE)
    other = tmp_path / "cam1.mp4"
    write_video(other, fps=60, seconds=3.0, clap_at=0.8, seed=5)

    assert ic.is_iphone_video(str(phone))
    assert check_videos.check([str(phone), str(other)]) == 0
    out = capsys.readouterr().out
    assert "lens    iPhone 17 Pro Max, iPhone 17 Pro Max back camera 2.22mm f/2.2, 14 mm (35 mm equiv.)" in out
    assert "0.5x ultra wide" in out
    assert "re-exported" not in out
    assert "no lens metadata (not an iPhone file)" in out          # the plain .mp4
