from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from motionboxpro.apps.recordings.models import Recording

from .models import Motion, MotionRecording, MotionVersion
from .rendering import STALE_AFTER_SECONDS, _after_render_exit, _finish, fail_stale_renders, mark_failed_if_active
from .serializers import MAX_RENDERS_PER_USER

BUSY_MESSAGE = "A render of this motion is still running. Wait until it has finished."
CAP_MESSAGE = f"You already have {MAX_RENDERS_PER_USER} renders running. Wait until one has finished."
STALE_MESSAGE = "The render stopped unexpectedly (no sign of life for over a minute)."


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


def seconds_ago(seconds):
    return timezone.now() - timedelta(seconds=seconds)


def set_times(version, **fields):
    """Sets timestamps with update(), since created_at can't be set through save()."""
    MotionVersion.objects.filter(pk=version.pk).update(**fields)
    version.refresh_from_db()


# stale enough, and fresh enough, with room to spare either side of STALE_AFTER_SECONDS
OLD = STALE_AFTER_SECONDS + 30
FRESH = STALE_AFTER_SECONDS - 30


# the render process is never started: the view only hands it the new version
@mock.patch("motionboxpro.apps.motions.views.start_render")
class StartRenderingBusyCheckTests(TestCase):
    """
    A render is refused while the same motion is queued or running, or while the user already has
    MAX_RENDERS_PER_USER renders queued or running across their motions. Other users' renders don't count.
    """

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

    def test_another_users_renders_do_not_count(self, _start_render):
        for i in range(MAX_RENDERS_PER_USER):
            make_version(make_motion(self.other_user, f"Theirs {i}"), MotionVersion.Status.RUNNING)

        self.assert_started(self.start(self.motion))

    def test_renders_of_other_motions_below_the_cap_do_not_block(self, _start_render):
        # queued and running both count toward the cap
        statuses = [MotionVersion.Status.RUNNING, MotionVersion.Status.QUEUED]
        for i in range(MAX_RENDERS_PER_USER - 1):
            make_version(make_motion(self.user, f"Other {i}"), statuses[i % 2])

        self.assert_started(self.start(self.motion))

    def test_renders_of_other_motions_at_the_cap_block(self, _start_render):
        statuses = [MotionVersion.Status.RUNNING, MotionVersion.Status.QUEUED]
        for i in range(MAX_RENDERS_PER_USER):
            make_version(make_motion(self.user, f"Other {i}"), statuses[i % 2])

        response = self.start(self.motion)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["non_field_errors"], [CAP_MESSAGE])
        self.assertFalse(self.motion.versions.exists())

    def test_finished_renders_of_other_motions_do_not_count(self, _start_render):
        for i in range(MAX_RENDERS_PER_USER):
            other = make_motion(self.user, f"Other {i}")
            make_version(other, MotionVersion.Status.DONE)
            make_version(other, MotionVersion.Status.FAILED)

        self.assert_started(self.start(self.motion))

    def test_dead_renders_of_other_motions_do_not_use_up_slots(self, _start_render):
        for i in range(MAX_RENDERS_PER_USER):
            dead = make_version(make_motion(self.user, f"Other {i}"), MotionVersion.Status.RUNNING)
            set_times(dead, heartbeat_at=seconds_ago(OLD))

        self.assert_started(self.start(self.motion))


class OneMotionTestCase(TestCase):
    """One user with one motion, and a check of a version's status and error as the database has them."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(email="owner@example.com", password="unused")
        self.motion = make_motion(self.user)

    def assert_status(self, version, status, error=""):
        version.refresh_from_db()
        self.assertEqual(version.status, status)
        self.assertEqual(version.error, error)


class StaleRenderTests(OneMotionTestCase):
    """A queued or running render with no sign of life for STALE_AFTER_SECONDS is marked failed."""

    def test_old_heartbeat_is_marked_failed(self):
        version = make_version(self.motion, MotionVersion.Status.RUNNING)
        set_times(version, heartbeat_at=seconds_ago(OLD))

        fail_stale_renders(self.motion.versions.all())

        self.assert_status(version, MotionVersion.Status.FAILED, STALE_MESSAGE)
        self.assertIsNotNone(version.finished_at)

    def test_fresh_heartbeat_is_left_alone(self):
        # created long ago, but beating: the heartbeat counts, not the creation
        version = make_version(self.motion, MotionVersion.Status.RUNNING)
        set_times(version, created_at=seconds_ago(OLD * 10), heartbeat_at=seconds_ago(FRESH))

        fail_stale_renders(self.motion.versions.all())

        self.assert_status(version, MotionVersion.Status.RUNNING)

    def test_done_is_left_alone(self):
        version = make_version(self.motion, MotionVersion.Status.DONE)
        set_times(version, created_at=seconds_ago(OLD), heartbeat_at=seconds_ago(OLD))

        fail_stale_renders(self.motion.versions.all())

        self.assert_status(version, MotionVersion.Status.DONE)

    def test_queued_without_heartbeat_and_old_creation_is_marked_failed(self):
        version = make_version(self.motion, MotionVersion.Status.QUEUED)
        set_times(version, created_at=seconds_ago(OLD))

        fail_stale_renders(self.motion.versions.all())

        self.assert_status(version, MotionVersion.Status.FAILED, STALE_MESSAGE)

    def test_queued_without_heartbeat_and_recent_creation_is_left_alone(self):
        version = make_version(self.motion, MotionVersion.Status.QUEUED)

        fail_stale_renders(self.motion.versions.all())

        self.assert_status(version, MotionVersion.Status.QUEUED)

    def test_only_the_given_queryset_is_checked(self):
        other = make_version(make_motion(self.user, "Other"), MotionVersion.Status.RUNNING)
        set_times(other, heartbeat_at=seconds_ago(OLD))

        fail_stale_renders(self.motion.versions.all())

        self.assert_status(other, MotionVersion.Status.RUNNING)

    def test_mark_failed_if_active_marks_queued_and_running(self):
        queued = make_version(self.motion, MotionVersion.Status.QUEUED)
        running = make_version(self.motion, MotionVersion.Status.RUNNING)

        mark_failed_if_active(queued.pk, "gone")
        mark_failed_if_active(running.pk, "gone")

        self.assert_status(queued, MotionVersion.Status.FAILED, "gone")
        self.assert_status(running, MotionVersion.Status.FAILED, "gone")

    def test_mark_failed_if_active_leaves_done_and_failed_alone(self):
        done = make_version(self.motion, MotionVersion.Status.DONE)
        failed = make_version(self.motion, MotionVersion.Status.FAILED)
        MotionVersion.objects.filter(pk=failed.pk).update(error="the pipeline's own error")

        mark_failed_if_active(done.pk, "gone")
        mark_failed_if_active(failed.pk, "gone")

        self.assert_status(done, MotionVersion.Status.DONE)
        self.assertIsNone(done.finished_at)
        self.assert_status(failed, MotionVersion.Status.FAILED, "the pipeline's own error")

    def test_finish_overwrites_failed_with_done(self):
        # the render process holds its version from before the stale check failed it, e.g. across machine sleep
        version = make_version(self.motion, MotionVersion.Status.RUNNING)
        mark_failed_if_active(version.pk, STALE_MESSAGE)

        _finish(version, MotionVersion.Status.DONE)

        self.assert_status(version, MotionVersion.Status.DONE)


@mock.patch("motionboxpro.apps.motions.views.start_render")
class StuckRenderClearedTests(OneMotionTestCase):
    """Opening a motion clears a render whose process died, so the motion can render again."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_detail_view_clears_stuck_version_so_next_render_starts(self, _start_render):
        stuck = make_version(self.motion, MotionVersion.Status.RUNNING)
        set_times(stuck, heartbeat_at=seconds_ago(OLD))

        detail = self.client.get(reverse("motion_detail", kwargs={"uuid": self.motion.uuid}))

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["versions"][0]["status"], MotionVersion.Status.FAILED)
        self.assertEqual(detail.json()["versions"][0]["error"], STALE_MESSAGE)

        url = reverse("motion_version_start", kwargs={"motion_uuid": self.motion.uuid})
        response = self.client.post(url, {"pose_model": "mediapipe"}, format="json")

        self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(self.motion.versions.filter(status=MotionVersion.Status.QUEUED).count(), 1)

    def test_list_view_clears_stuck_versions_of_own_motions(self, _start_render):
        stuck = make_version(self.motion, MotionVersion.Status.RUNNING)
        set_times(stuck, heartbeat_at=seconds_ago(OLD))

        response = self.client.get(reverse("motion_list"))

        self.assertEqual(response.status_code, 200)
        stuck.refresh_from_db()
        self.assertEqual(stuck.status, MotionVersion.Status.FAILED)


class RenderExitWatcherTests(OneMotionTestCase):
    """Once the render process has exited, a version still queued or running is marked failed."""

    def test_running_with_exit_code_1_is_marked_failed(self):
        version = make_version(self.motion, MotionVersion.Status.RUNNING)

        _after_render_exit(version.pk, 1)

        self.assert_status(
            version, MotionVersion.Status.FAILED, "The render process stopped unexpectedly (exit code 1)."
        )
        self.assertIsNotNone(version.finished_at)

    def test_negative_exit_code_names_the_signal(self):
        version = make_version(self.motion, MotionVersion.Status.RUNNING)

        _after_render_exit(version.pk, -9)

        self.assert_status(
            version, MotionVersion.Status.FAILED, "The render process stopped unexpectedly (killed by signal 9)."
        )

    def test_exit_code_0_while_still_running_is_marked_failed(self):
        version = make_version(self.motion, MotionVersion.Status.RUNNING)

        _after_render_exit(version.pk, 0)

        self.assert_status(
            version, MotionVersion.Status.FAILED, "The render process stopped unexpectedly (exit code 0)."
        )

    def test_queued_is_marked_failed(self):
        # the process died before it switched the version to running
        version = make_version(self.motion, MotionVersion.Status.QUEUED)

        _after_render_exit(version.pk, 1)

        self.assert_status(
            version, MotionVersion.Status.FAILED, "The render process stopped unexpectedly (exit code 1)."
        )

    def test_done_is_left_alone(self):
        version = make_version(self.motion, MotionVersion.Status.DONE)

        _after_render_exit(version.pk, 0)

        self.assert_status(version, MotionVersion.Status.DONE)
        self.assertIsNone(version.finished_at)
