import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from motionboxpro.apps.motions.models import Motion, MotionRecording
from motionboxpro.apps.motions.serializers import MotionSerializer, StartRenderingSerializer
from motionboxpro.apps.recordings.models import Performer, Recording


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RenderHeightTests(TestCase):
    """Which height a render uses: the first camera, by slot, whose recording has one."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(email="owner@example.com", password="x")
        self.motion = Motion.objects.create(owner=self.user, name="Walk")

    def add_camera(self, slot, performer=None, own_height=None):
        recording = Recording(owner=self.user, name=f"Cam {slot}", performer=performer, performer_height=own_height)
        recording.video.save(f"cam{slot}.mp4", ContentFile(b"video"), save=False)
        recording.save()
        MotionRecording.objects.create(motion=self.motion, recording=recording, camera_slot=slot)

    def start_render(self):
        return StartRenderingSerializer(data={}, context={"motion": self.motion})

    def test_no_height_blocks_the_render(self):
        self.add_camera(0)
        self.add_camera(1)

        serializer = self.start_render()

        self.assertFalse(serializer.is_valid())
        self.assertIn("Set a height on one of the recordings first.", str(serializer.errors))
        self.assertIsNone(MotionSerializer(self.motion).data["render_height"])

    def test_recording_without_performer_uses_its_own_height(self):
        self.add_camera(0)
        self.add_camera(1, own_height=1.8)

        serializer = self.start_render()

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["height_m"], 1.8)
        self.assertEqual(MotionSerializer(self.motion).data["render_height"], {"height_m": 1.8, "camera_slot": 1})

    def test_lowest_camera_slot_with_a_height_wins(self):
        performer = Performer.objects.create(owner=self.user, full_name="Alex", height_m=1.6)
        self.add_camera(0, own_height=1.9)
        self.add_camera(1, performer=performer)

        serializer = self.start_render()

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["height_m"], 1.9)

    def test_performer_without_height_hides_the_recordings_own_height(self):
        performer = Performer.objects.create(owner=self.user, full_name="Alex", height_m=None)
        self.add_camera(0, performer=performer, own_height=1.7)
        self.add_camera(1)

        self.assertFalse(self.start_render().is_valid())
