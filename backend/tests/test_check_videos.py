"""
check_videos and the clap detector on synthetic videos with known clap times.
Encodes three short videos (about a second) per test session.
"""
import pytest

from mocap_pipeline import check_videos
from mocap_pipeline.stage2_reconstruct import sync
from tests.synthetic_video import write_video


@pytest.fixture(scope="module")
def videos(tmp_path_factory):
    d = tmp_path_factory.mktemp("synth")
    write_video(d / "cam0.mp4", fps=60, seconds=4.0, clap_at=1.20, seed=0)
    write_video(d / "cam1.mp4", fps=30, seconds=4.0, clap_at=0.85, seed=1)
    write_video(d / "noclap.mp4", fps=30, seconds=4.0, clap_at=None, seed=2)
    return {p.stem: str(p) for p in d.iterdir()}


def test_clap_detector_finds_claps_within_10ms(videos):
    claps = sync.detect_claps([videos["cam0"], videos["cam1"]])
    assert abs(claps[0] - 1.20) < 0.010
    assert abs(claps[1] - 0.85) < 0.010


def test_clap_detector_rejects_silence(videos):
    with pytest.raises(sync.ClapNotFoundError):
        sync.detect_claps([videos["noclap"]])


def test_check_passes_good_take(videos, capsys):
    assert check_videos.check([videos["cam0"], videos["cam1"]]) == 0
    out = capsys.readouterr().out
    assert "640x360, 60.00 fps" in out
    assert "clap    1.19" in out or "clap    1.20" in out
    assert "frame rates differ" in out          # 60 and 30 in one take
    assert "All files usable" in out


def test_check_fails_clapless_video(videos, capsys):
    assert check_videos.check([videos["cam0"], videos["noclap"]]) == 1
    out = capsys.readouterr().out
    assert "FAIL    no clap" in out
    assert "1 file(s) the pipeline cannot use" in out


def test_check_fails_unreadable_file(tmp_path, videos, capsys):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    assert check_videos.check([videos["cam0"], str(bad)]) == 1
    assert "cannot be opened" in capsys.readouterr().out
