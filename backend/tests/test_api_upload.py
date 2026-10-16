"""
api.py's upload checks, without a server: check_upload only reads .videos and
.fields, so a stand-in object is enough. Camera fields are cam0, cam1, ... with
no gaps and no maximum (D-024); the minimum of 2 stays (D-002).
"""
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
api = pytest.importorskip("api")


def upload(cameras, **fields):
    fields.setdefault("height_m", "1.75")
    return SimpleNamespace(videos={c: f"/takes/x/{c}.mp4" for c in cameras}, fields=fields)


def test_field_pattern():
    assert api.CAMERA_FIELD_RE.match("cam0") and api.CAMERA_FIELD_RE.match("cam12")
    assert not api.CAMERA_FIELD_RE.match("camera") and not api.CAMERA_FIELD_RE.match("cam-1")
    assert api.camera_number("cam12") == 12


def test_eleven_cameras_in_numeric_order():
    cams = [f"cam{c}" for c in range(11)]
    paths, height, name, project = api.check_upload(upload(reversed(cams)))
    assert paths == [f"/takes/x/{c}.mp4" for c in cams]       # cam10 after cam9, not after cam1
    assert height == 1.75 and name is None and project is None


@pytest.mark.parametrize("cams", [["cam0"], ["cam0", "cam2"], ["cam1", "cam2"], []])
def test_too_few_or_gapped_cameras_rejected(cams):
    with pytest.raises(api.UploadError) as e:
        api.check_upload(upload(cams))
    assert e.value.status_code == 422 and "at least 2" in e.value.detail
