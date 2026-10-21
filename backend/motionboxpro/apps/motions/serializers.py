from django.db import transaction
from django.db.models import Max
from rest_framework import serializers

from motionboxpro.apps.projects.models import Project, ProjectMotion
from motionboxpro.apps.recordings.models import Recording

from .models import Motion, MotionRecording, MotionVersion

# Camera slots run 0 to 3, so a motion has at most four cameras (see MotionRecording.camera_slot)
MIN_CAMERAS = 2
MAX_CAMERAS = 4


def performer_data(performer):
    if performer is None:
        return None

    return {"id": performer.pk, "full_name": performer.full_name, "height_m": performer.height_m}


class MotionSerializer(serializers.ModelSerializer):
    """
    A motion in the logged-in user's list. It can go into one of the user's projects when
    created, or none; it can be in several projects, listed in `projects`. Its cameras
    (`recordings`) and the performers in them come from the recordings it uses.
    """

    # Optional: the project to put the new motion in, by its public id (only the user's own projects, see __init__)
    project = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=Project.objects.none(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    projects = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    recording_count = serializers.IntegerField(read_only=True)
    recordings = serializers.SerializerMethodField()
    performers = serializers.SerializerMethodField()
    versions = serializers.SerializerMethodField()

    class Meta:
        model = Motion
        fields = (
            "uuid",
            "name",
            "project",
            "projects",
            "status",
            "recording_count",
            "recordings",
            "performers",
            "versions",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uuid", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["project"].queryset = Project.objects.filter(owner=request.user)

    def _camera_links(self, obj):
        return obj.motion_recordings.select_related("recording__performer").order_by("camera_slot")

    def get_projects(self, obj):
        links = obj.project_links.select_related("project").order_by("project__name")

        return [{"uuid": str(link.project.uuid), "name": link.project.name} for link in links]

    def get_recordings(self, obj):
        # uuid is the link's (the camera's); recording is the recording's own
        return [
            {
                "uuid": str(link.uuid),
                "recording": str(link.recording.uuid),
                "name": link.recording.name,
                "camera_slot": link.camera_slot,
                "width": link.recording.width,
                "height": link.recording.height,
                "fps": link.recording.fps,
                "duration_s": link.recording.duration_s,
                "performer": performer_data(link.recording.performer),
            }
            for link in self._camera_links(obj)
        ]

    def get_performers(self, obj):
        found = {}
        for link in self._camera_links(obj):
            performer = link.recording.performer
            if performer is not None and performer.pk not in found:
                found[performer.pk] = performer_data(performer)

        return list(found.values())

    def get_versions(self, obj):
        return [
            {
                "uuid": str(v.uuid),
                "number": v.number,
                "source": v.source,
                "label": v.label,
                "pose_model": v.pose_model,
                "status": v.status,
                "error": v.error,
                "created_at": v.created_at.isoformat(),
            }
            for v in obj.versions.order_by("number")
        ]

    def create(self, validated_data):
        project = validated_data.pop("project", None)
        validated_data["owner"] = self.context["request"].user

        # The motion and its place in the project are saved together, or not at all
        with transaction.atomic():
            motion = super().create(validated_data)
            if project is not None:
                ProjectMotion.objects.create(project=project, motion=motion, order=project.project_motions.count())

        return motion


class MotionRecordingsSetSerializer(serializers.Serializer):
    """
    The whole set of recordings a motion uses: two to four of the logged-in user's. Cameras
    whose recording stays keep their slot; new ones take the free slots. The motion is the instance.
    """

    recordings = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=MIN_CAMERAS,
        max_length=MAX_CAMERAS,
    )

    def validate_recordings(self, uuids):
        if self.context["motion"].versions.exists():
            raise serializers.ValidationError("This motion already has versions, so its recordings are locked.")
        if len(set(uuids)) != len(uuids):
            raise serializers.ValidationError("A recording can be used only once.")

        found = {r.uuid: r for r in Recording.objects.filter(owner=self.context["request"].user, uuid__in=uuids)}
        if len(found) != len(uuids):
            raise serializers.ValidationError("Some of these recordings are not yours.")

        return [found[u] for u in uuids]

    def update(self, motion, validated_data):
        wanted = validated_data["recordings"]
        wanted_ids = {r.pk for r in wanted}

        with transaction.atomic():
            links = list(motion.motion_recordings.all())
            for link in links:
                if link.recording_id not in wanted_ids:
                    link.delete()

            kept = {link.recording_id: link for link in links if link.recording_id in wanted_ids}
            free_slots = [s for s in range(MAX_CAMERAS) if s not in {link.camera_slot for link in kept.values()}]
            for recording in wanted:
                if recording.pk not in kept:
                    MotionRecording.objects.create(motion=motion, recording=recording, camera_slot=free_slots.pop(0))

        return motion


class MotionProjectAddSerializer(serializers.Serializer):
    """Puts a motion into one of the logged-in user's projects. The motion comes from the view."""

    project = serializers.SlugRelatedField(slug_field="uuid", queryset=Project.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["project"].queryset = Project.objects.filter(owner=request.user)

    def validate_project(self, project):
        motion = self.context["motion"]
        if motion.project_links.filter(project=project).exists():
            raise serializers.ValidationError("The motion is already in this project.")

        return project

    def create(self, validated_data):
        project = validated_data["project"]
        motion = self.context["motion"]

        return ProjectMotion.objects.create(project=project, motion=motion, order=project.project_motions.count())


class StartRenderingSerializer(serializers.Serializer):
    """
    Renders the motion as a new version. The motion comes from the view. Checks that the
    motion has enough cameras, that no other render is running, and that a performer's
    height is known; the height is what the pipeline needs.
    """

    pose_model = serializers.ChoiceField(choices=MotionVersion.PoseModel.choices, default=MotionVersion.PoseModel.MEDIAPIPE)

    def validate(self, attrs):
        motion = self.context["motion"]
        links = list(motion.motion_recordings.select_related("recording__performer").order_by("camera_slot"))

        if len(links) < MIN_CAMERAS:
            raise serializers.ValidationError(f"Add at least {MIN_CAMERAS} recordings to the motion before rendering.")

        busy = MotionVersion.objects.filter(status__in=[MotionVersion.Status.QUEUED, MotionVersion.Status.RUNNING])
        if busy.exists():
            raise serializers.ValidationError("Another render is still running. Wait until it has finished.")

        height = next(
            (link.recording.performer.height_m for link in links if link.recording.performer and link.recording.performer.height_m),
            None,
        )
        if height is None:
            raise serializers.ValidationError("Set a performer with a height on one of the recordings first.")

        attrs["height_m"] = height

        return attrs

    def create(self, validated_data):
        motion = self.context["motion"]

        with transaction.atomic():
            last = motion.versions.aggregate(last=Max("number"))["last"] or 0

            return MotionVersion.objects.create(
                motion=motion,
                number=last + 1,
                source=MotionVersion.Source.PIPELINE,
                pose_model=validated_data["pose_model"],
                height_m=validated_data["height_m"],
                status=MotionVersion.Status.QUEUED,
            )
