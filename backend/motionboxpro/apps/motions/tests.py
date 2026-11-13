from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from motionboxpro.apps.recordings.models import Recording

from .models import Motion, MotionRecording, MotionVersion

BUSY_MESSAGE = "A render of this motion is still running. Wait until it has finished."


def make_motion(owner, name="Motion"):
    """A motion with two cameras and a height, so only the busy check can stop a render."""
    motion = Motion.objects.create(owner=owner, name=name)
    for slot in range(2):
        recording = Recording.objects.create(owner=owner, video=f"videos/{name}-{slot}.mp4", performer_height=1.8)
        MotionRecording.objects.create(motion=motion, recording=recording, camera_slot=slot)

    return motion


def make_version(motion, status):
    number = motion.versions.count() + 1

    return MotionVersion.objects.create(motion=motion, number=number, height_m=1.8, status=status)


# the render process is never started: the view only hands it the new version
@mock.patch("motionboxpro.apps.motions.views.start_render")
class StartRenderingBusyCheckTests(TestCase):
    """A render is refused only while another render of the same motion is queued or running."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="owner@example.com", password="unused")
        self.other_user = User.objects.create_user(email="other@example.com", password="unused")
        self.motion = make_motion(self.user, "Mine")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def start(self, motion):
        url = reverse("motion_version_start", kwargs={"motion_uuid": motion.uuid})

        return self.client.post(url, {"pose_model": "mediapipe"}, format="json")

    def assert_started(self, response):
        self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(self.motion.versions.filter(status=MotionVersion.Status.QUEUED).count(), 1)

    def test_queued_version_of_this_motion_blocks(self, _start_render):
        make_version(self.motion, MotionVersion.Status.QUEUED)

        response = self.start(self.motion)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["non_field_errors"], [BUSY_MESSAGE])
        self.assertEqual(self.motion.versions.count(), 1)

    def test_running_version_of_this_motion_blocks(self, _start_render):
        make_version(self.motion, MotionVersion.Status.RUNNING)

        response = self.start(self.motion)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["non_field_errors"], [BUSY_MESSAGE])
        self.assertEqual(self.motion.versions.count(), 1)

    def test_finished_versions_of_this_motion_do_not_block(self, _start_render):
        make_version(self.motion, MotionVersion.Status.DONE)
        make_version(self.motion, MotionVersion.Status.FAILED)

        response = self.start(self.motion)

        self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(self.motion.versions.count(), 3)

    def test_running_version_of_another_users_motion_does_not_block(self, _start_render):
        make_version(make_motion(self.other_user, "Theirs"), MotionVersion.Status.RUNNING)

        self.assert_started(self.start(self.motion))

    def test_running_version_of_same_users_other_motion_does_not_block(self, _start_render):
        make_version(make_motion(self.user, "Other"), MotionVersion.Status.RUNNING)

        self.assert_started(self.start(self.motion))
