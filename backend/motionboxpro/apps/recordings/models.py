import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from motionboxpro.utils.files import file_path


class Performer(models.Model):
    """
    Someone who moves in front of the cameras, kept in their owner's list. Not a user:
    the performer has no login of their own.
    """

    # The account that keeps this performer in its list
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="performers",
    )
    full_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    # Default height for new recordings of this performer
    height_m = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1.0), MaxValueValidator(2.5)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "full_name"], name="unique_performer_name_per_owner"),
        ]

    def __str__(self):
        return self.full_name


class Recording(models.Model):
    """
    One video from one camera. A recording on its own belongs to no motion. Which motions
    it is used in is kept in motions.MotionRecording.
    """

    class LensSource(models.TextChoices):
        """Where the camera's lens data comes from: read from an iPhone video, or entered as a field of view."""

        METADATA = "metadata", "From video metadata (iPhone)"
        FIELD_OF_VIEW = "field_of_view", "Field of view entered"

    # Public id for links (e.g. /recordings/<uuid>); the integer id stays internal
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recordings",
    )
    # Who is in the footage. Empty if it is not recorded.
    performer = models.ForeignKey(
        Performer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recordings",
    )

    name = models.CharField(max_length=100, blank=True)
    video = models.FileField(upload_to=file_path)
    # Preview image taken from the video at upload, so lists don't need to load the video
    thumbnail = models.FileField(upload_to=file_path, blank=True)

    lens_source = models.CharField(max_length=20, choices=LensSource.choices, blank=True)
    # Only when the lens source is a field of view entered by hand
    field_of_view_deg = models.FloatField(null=True, blank=True)

    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    fps = models.FloatField(null=True, blank=True)
    duration_s = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or f"Recording {self.pk}"
