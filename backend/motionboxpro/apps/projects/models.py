import uuid

from django.conf import settings
from django.db import models


class Project(models.Model):
    """
    A folder of motions for one sport or purpose. Which motions it holds, and in what
    order, is in ProjectMotion.
    """

    # Public id for links (e.g. /projects/<uuid>); the integer id stays internal
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=60, blank=True, default="Other")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class ProjectMotion(models.Model):
    """Which project a motion sits in, and where it is in that project. Each motion is in one project."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="project_motions",
    )
    motion = models.ForeignKey(
        "motions.Motion",
        on_delete=models.CASCADE,
        related_name="project_links",
    )
    # Position of the motion within its project, for moving motions around
    order = models.PositiveSmallIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "added_at"]
        constraints = [
            models.UniqueConstraint(fields=["motion"], name="one_project_per_motion"),
        ]

    def __str__(self):
        return f"{self.motion} in {self.project}"
