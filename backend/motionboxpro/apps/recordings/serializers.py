from pathlib import Path

from rest_framework import serializers

from .models import Performer, Recording
from .video import read_video


class PerformerSerializer(serializers.ModelSerializer):
    """A performer in the logged-in user's list."""

    class Meta:
        model = Performer
        fields = ("id", "full_name", "email", "phone", "height_m", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_full_name(self, value):
        owner = self.context["request"].user
        same_name = Performer.objects.filter(owner=owner, full_name=value)
        if self.instance is not None:
            same_name = same_name.exclude(pk=self.instance.pk)
        if same_name.exists():
            raise serializers.ValidationError("You already have a performer with this name.")

        return value

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user

        return super().create(validated_data)


class RecordingSerializer(serializers.ModelSerializer):
    """What the API returns for a recording. The name, lens settings and performer can be changed; the video cannot."""

    # The performer is chosen by id, and only from the logged-in user's own list (see __init__)
    has_thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Recording
        fields = (
            "uuid",
            "name",
            "performer",
            "lens_source",
            "field_of_view_deg",
            "width",
            "height",
            "fps",
            "duration_s",
            "has_thumbnail",
            "created_at",
        )
        read_only_fields = ("uuid", "width", "height", "fps", "duration_s", "created_at")

    def get_has_thumbnail(self, obj):
        return bool(obj.thumbnail)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["performer"].queryset = Performer.objects.filter(owner=request.user)


class RecordingUploadSerializer(serializers.ModelSerializer):
    """Creating a recording: upload one video. The name defaults to the file name, and the video is read at once."""

    has_thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Recording
        fields = ("uuid", "name", "video", "has_thumbnail", "created_at")
        read_only_fields = ("uuid", "created_at")

    def get_has_thumbnail(self, obj):
        return bool(obj.thumbnail)

    def create(self, validated_data):
        video = validated_data["video"]
        if not validated_data.get("name"):
            validated_data["name"] = Path(video.name).stem[:100]
        validated_data["owner"] = self.context["request"].user

        recording = super().create(validated_data)
        try:
            read_video(recording)
        except ValueError as error:
            recording.video.delete(save=False)
            recording.delete()
            raise serializers.ValidationError({"video": str(error)})

        return recording
