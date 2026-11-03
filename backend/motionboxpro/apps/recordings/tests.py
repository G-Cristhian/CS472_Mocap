import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from motionboxpro.apps.recordings.models import Performer, Recording
from motionboxpro.apps.recordings.serializers import RecordingSerializer


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RecordingEditTests(TestCase):
    """What the recording API accepts when a recording's performer or height is changed."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(email="owner@example.com", password="x")
        self.request = APIRequestFactory().patch("/")
        self.request.user = self.user
        self.recording = Recording(owner=self.user, name="Cam 0")
        self.recording.video.save("cam0.mp4", ContentFile(b"video"), save=False)
        self.recording.save()

    def edit(self, data):
        return RecordingSerializer(self.recording, data=data, partial=True, context={"request": self.request})

    def test_height_must_be_between_1_and_2_5_metres(self):
        for height, accepted in [(0.5, False), (3.0, False), (1.0, True), (1.75, True), (2.5, True), (None, True)]:
            with self.subTest(height=height):
                self.assertEqual(self.edit({"performer_height": height}).is_valid(), accepted)

    def test_another_users_performer_cannot_be_chosen(self):
        other = get_user_model().objects.create_user(email="other@example.com", password="x")
        theirs = Performer.objects.create(owner=other, full_name="Sam", height_m=1.6)

        serializer = self.edit({"performer": theirs.pk})

        self.assertFalse(serializer.is_valid())
        self.assertIn("performer", serializer.errors)
