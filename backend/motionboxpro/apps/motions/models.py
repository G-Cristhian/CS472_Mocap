import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from motionboxpro.utils.files import file_path


class Motion(models.Model):
    """
    One motion: 2 to 4 recordings of the same performance, processed together by the
    pipeline into a skeleton you can play back and export as .bvh. The recordings it
    uses are in MotionRecording; the project it sits in is in ProjectMotion. Its outputs,
    the pipeline runs and any manual edits, are MotionVersion rows.
    """

    class Status(models.TextChoices):
        """Progress of the motion. Derived from its latest pipeline version; draft until one exists."""

        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    # Public id for links (e.g. /motions/<uuid>); the integer id stays internal
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="motions",
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    # Set on every save, e.g. when the motion is renamed
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def status(self):
        """Progress of the latest pipeline run, or draft if the motion has never been processed."""
        latest = self.versions.filter(source=MotionVersion.Source.PIPELINE).order_by("-created_at").first()

        return latest.status if latest else Motion.Status.DRAFT

    @property
    def recording_count(self):
        return self.motion_recordings.count()

    @property
    def last_updated(self):
        """The latest change to any of the motion's versions. Before any version exists, the creation time."""
        latest = self.versions.order_by("-updated_at").values_list("updated_at", flat=True).first()

        return latest or self.created_at

    def __str__(self):
        return self.name


class MotionVersion(models.Model):
    """
    One output of a motion: a pipeline run, or a manual edit of an earlier version. A
    pipeline run has its own settings, progress, calibration and log; a manual edit has
    none of these and reads them from its parent. Each version keeps its own full
    out3d.json, so versions can be compared side by side.
    """

    class Source(models.TextChoices):
        PIPELINE = "pipeline", "Pipeline"
        MANUAL = "manual", "Manual edit"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    class Stage(models.TextChoices):
        DETECTING = "detecting", "Detecting joints"
        CALIBRATING = "calibrating", "Calibrating cameras"
        TRIANGULATING = "triangulating", "Triangulating"
        WRITING = "writing", "Writing files"

    class PoseModel(models.TextChoices):
        """The pose detector used in stage 1. Matches the backends in mocap_pipeline/stage1_keypoints/backends.py."""

        MEDIAPIPE = "mediapipe", "MediaPipe"
        RTMPOSE = "rtmpose", "RTMPose"

    # Public id for links to one version; the integer id stays internal
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    motion = models.ForeignKey(
        Motion,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    # Version number within the motion, unique per motion.
    number = models.PositiveSmallIntegerField()
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.PIPELINE)
    # The version this one was edited from; empty for a pipeline run
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    label = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Set on every save, e.g. when points are edited
    updated_at = models.DateTimeField(auto_now=True)
    # When the pipeline finished this run (pipeline versions only). Processing time needs a started_at too (not added yet)
    finished_at = models.DateTimeField(null=True, blank=True)

    # Pipeline settings and progress. A manual edit leaves these empty and uses its parent's.
    # Limits match backend/api.py (MIN/MAX_HEIGHT_M)
    height_m = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1.0), MaxValueValidator(2.5)],
    )
    pose_model = models.CharField(max_length=20, choices=PoseModel.choices, default=PoseModel.MEDIAPIPE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    stage = models.CharField(max_length=20, choices=Stage.choices, null=True, blank=True)
    error = models.TextField(blank=True)

    # Outputs of the run, kept in the database (the pipeline writes them to a temporary folder, which is then deleted)
    calibration = models.JSONField(null=True, blank=True)
    log = models.TextField(blank=True)
    out3d = models.JSONField(null=True, blank=True)  # the 3D joints, frame by frame
    bvh = models.TextField(blank=True)  # the skeleton animation, what the viewer plays
    metrics = models.JSONField(null=True, blank=True)

    # Summary of this version's out3d.json
    fps = models.FloatField(null=True, blank=True)
    frame_count = models.PositiveIntegerField(null=True, blank=True)
    duration_s = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["motion", "number"]
        constraints = [
            models.UniqueConstraint(fields=["motion", "number"], name="unique_version_number_per_motion"),
        ]

    def __str__(self):
        return f"{self.motion} v{self.number}"


class MotionRecording(models.Model):
    """
    A recording used in a motion, as one camera of it. Slot 0 is the reference camera,
    up to 3 (4 cameras). The clap time, reprojection error and keypoints depend on the
    motion's processing, so they live here and not on the recording.
    """

    # Public id for this link; the integer id stays internal
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    motion = models.ForeignKey(
        Motion,
        on_delete=models.CASCADE,
        related_name="motion_recordings",
    )
    recording = models.ForeignKey(
        "recordings.Recording",
        on_delete=models.CASCADE,
        related_name="motion_links",
    )
    camera_slot = models.PositiveSmallIntegerField(validators=[MaxValueValidator(3)])

    # Set by the pipeline when the motion is processed
    clap_time_s = models.FloatField(null=True, blank=True)
    reprojection_error_px = models.FloatField(null=True, blank=True)
    keypoints_npz = models.FileField(upload_to=file_path, blank=True)

    class Meta:
        ordering = ["camera_slot"]
        constraints = [
            models.UniqueConstraint(fields=["motion", "recording"], name="unique_recording_per_motion"),
            models.UniqueConstraint(fields=["motion", "camera_slot"], name="unique_camera_slot_per_motion"),
        ]

    def __str__(self):
        return f"{self.motion} · cam{self.camera_slot}"
