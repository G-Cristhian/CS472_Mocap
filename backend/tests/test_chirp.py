"""
The sync chirp (stage2_reconstruct/chirp.py): finding it in audio arrays with
noise, echoes and a clap nearby, rejecting audio without it or with it twice,
then end to end through AAC-encoded synthetic videos and synchronise().
"""
import wave

import numpy as np
import pytest

from mocap_pipeline import check_videos, config
from mocap_pipeline.stage2_reconstruct import chirp, sync
from tests.conftest import make_keypoints
from tests.synthetic_video import write_video

RATE = config.CLAP_AUDIO_RATE


def room(seconds=6.0, seed=0, noise=0.05):
    return np.random.default_rng(seed).normal(0, noise, int(seconds * RATE))


def add_chirp(audio, at_s, gain=0.3, echoes=()):
    """echoes: (delay_s, gain) reflections of the chirp, as off walls."""
    sweep = chirp.chirp_template(RATE)
    for delay, g in ((0.0, 1.0), *echoes):
        s = int(round((at_s + delay) * RATE))
        audio[s:s + len(sweep)] += gain * g * sweep[:len(audio) - s]
    return audio


def test_template_matches_the_config():
    sweep = chirp.chirp_template(RATE)
    assert len(sweep) == int(round(config.CHIRP_DURATION_S * RATE))
    assert np.abs(sweep).max() <= 1.0
    assert abs(sweep[0]) < 1e-9 and abs(sweep[-1]) < 0.01    # faded in and out, no click


def test_finds_the_chirp_to_a_fraction_of_a_millisecond():
    audio = add_chirp(room(), 2.345)
    assert abs(chirp.find_chirp_in_audio(audio, RATE, "a") - 2.345) < 0.0005


def test_finds_a_chirp_quieter_than_the_room():
    # rms of the chirp about 0.035 against 0.05 noise: a clap this weak would be lost
    audio = add_chirp(room(seed=1), 1.5, gain=0.05)
    assert abs(chirp.find_chirp_in_audio(audio, RATE, "a") - 1.5) < 0.001


def test_echoes_and_a_clap_do_not_move_it():
    audio = add_chirp(room(seed=2), 3.0, echoes=((0.006, 0.6), (0.017, 0.4), (0.04, 0.3)))
    audio[int(2.0 * RATE):int(2.0 * RATE) + 240] += np.random.default_rng(3).normal(0, 3, 240)  # a clap
    assert abs(chirp.find_chirp_in_audio(audio, RATE, "a") - 3.0) < 0.001


def test_no_chirp_is_reported_with_its_score():
    with pytest.raises(chirp.ChirpNotFoundError) as info:
        chirp.find_chirp_in_audio(room(), RATE, "cam1.mov")
    message = str(info.value)
    assert message.startswith("cam1.mov: no chirp") and "(need 0.20" in message
    assert "--clap-threshold 0.5" in message


def test_digital_silence_is_not_a_match():
    with pytest.raises(chirp.ChirpNotFoundError):
        chirp.find_chirp_in_audio(np.zeros(5 * RATE), RATE, "a")


def test_chirp_played_twice_is_ambiguous():
    audio = add_chirp(add_chirp(room(), 1.0), 3.0)
    with pytest.raises(chirp.ChirpNotFoundError, match="heard twice, at 1.00 s and 3.00 s"):
        chirp.find_chirp_in_audio(audio, RATE, "a")


def test_a_missing_chirp_is_a_missing_sync_mark():
    # run_pipeline catches sync.ClapNotFoundError for both signals
    assert issubclass(chirp.ChirpNotFoundError, sync.ClapNotFoundError)


def test_wav_holds_the_chirp_half_a_second_in(tmp_path):
    path = tmp_path / "chirp.wav"
    chirp.write_chirp_wav(str(path), rate=RATE)
    with wave.open(str(path)) as f:
        assert (f.getnchannels(), f.getsampwidth(), f.getframerate()) == (1, 2, RATE)
        audio = np.frombuffer(f.readframes(f.getnframes()), "<i2") / 32767.0
    assert abs(chirp.find_chirp_in_audio(audio, RATE, "wav") - 0.5) < 0.0005


@pytest.fixture(scope="module")
def videos(tmp_path_factory):
    d = tmp_path_factory.mktemp("chirp")
    # a clap in every video too, in a different place: the signal decides which is used. The
    # chirp is loud (100x the room noise); its slow fade-in keeps the clap search off it.
    write_video(d / "cam0.mp4", fps=60, seconds=4.0, clap_at=0.5, chirp_at=1.20, seed=0)
    write_video(d / "cam1.mp4", fps=30, seconds=4.0, clap_at=0.3, chirp_at=0.85, seed=1)
    write_video(d / "nochirp.mp4", fps=30, seconds=4.0, clap_at=1.0, seed=2)
    return {p.stem: str(p) for p in d.iterdir()}


def test_chirp_survives_aac(videos):
    # AAC (what phones record) shifts and smears audio a little; the match still lands within 2 ms
    times = sync.detect_sync_times([videos["cam0"], videos["cam1"]], signal="chirp")
    assert abs(times[0] - 1.20) < 0.002 and abs(times[1] - 0.85) < 0.002


def test_signal_picks_the_mark(videos):
    claps = sync.detect_sync_times([videos["cam0"], videos["cam1"]], signal="clap")
    assert abs(claps[0] - 0.5) < 0.010 and abs(claps[1] - 0.3) < 0.010
    with pytest.raises(ValueError, match="signal must be one of"):
        sync.detect_sync_times([videos["cam0"]], signal="whistle")


def test_video_without_the_chirp_fails(videos):
    with pytest.raises(sync.ClapNotFoundError, match="nochirp.mp4: no chirp"):
        sync.detect_sync_times([videos["cam0"], videos["nochirp"]], signal="chirp")


def test_synchronise_with_the_chirp(videos):
    kps = [make_keypoints("cam0", videos["cam0"], frames=240), make_keypoints("cam1", videos["cam1"], frames=120)]
    kps[0].fps, kps[0].timestamps = 60.0, np.arange(240) / 60.0
    kps[1].fps, kps[1].timestamps = 30.0, np.arange(120) / 30.0
    result, resampled = sync.synchronise([videos["cam0"], videos["cam1"]], kps, signal="chirp")
    assert abs(result.clap_time_s["cam0"] - 1.20) < 0.002
    assert abs(result.clap_time_s["cam1"] - 0.85) < 0.002
    # the shared clock starts at the chirp and ends when the first video does
    assert result.common_timestamps[0] == 0.0
    assert result.common_timestamps[-1] <= min(4.0 - 1.20, 4.0 - 0.85)


def test_check_videos_with_the_chirp(videos, capsys):
    assert check_videos.check([videos["cam0"], videos["cam1"]], signal="chirp") == 0
    out = capsys.readouterr().out
    assert "chirp   1.20" in out and "All files usable" in out
    assert check_videos.check([videos["cam0"], videos["nochirp"]], signal="chirp") == 1
    assert "FAIL    no chirp" in capsys.readouterr().out
