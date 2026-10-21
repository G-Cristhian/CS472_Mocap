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
    """
    Puts a motion in a project, and says where it sits there. A motion can be in several
    projects, or in none; a project holds any number of motions.
    """

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
            models.UniqueConstraint(fields=["project", "motion"], name="unique_motion_per_project"),
        ]

    def __str__(self):
        return f"{self.motion} in {self.project}"
