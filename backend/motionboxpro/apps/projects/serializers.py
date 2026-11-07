from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    """A project in the logged-in user's list."""

    class Meta:
        model = Project
        fields = ("uuid", "name", "category", "created_at", "updated_at")
        read_only_fields = ("uuid", "created_at", "updated_at")

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user

        return super().create(validated_data)
