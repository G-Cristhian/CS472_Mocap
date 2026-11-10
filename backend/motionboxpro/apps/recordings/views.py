import mimetypes

from django.http import FileResponse, Http404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Performer, Recording
from .serializers import PerformerSerializer, RecordingSerializer, RecordingUploadSerializer
from .video import read_video


class OwnRecordingsMixin:
    """Only logged-in users, and only their own recordings. Anyone else gets 'not found'."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Recording.objects.filter(owner=self.request.user).order_by("-created_at")


class RecordingListCreateView(OwnRecordingsMixin, generics.ListCreateAPIView):
    """GET: the logged-in user's recordings. POST: upload one video as a new recording."""

    def get_serializer_class(self):
        return RecordingUploadSerializer if self.request.method == "POST" else RecordingSerializer


class RecordingDetailView(OwnRecordingsMixin, generics.RetrieveUpdateDestroyAPIView):
    """GET, PATCH (name, lens settings, performer) and DELETE for one of the logged-in user's recordings."""

    serializer_class = RecordingSerializer
    lookup_field = "uuid"


class RecordingVideoView(OwnRecordingsMixin, generics.GenericAPIView):
    """The video file of one of the logged-in user's recordings. Served through the API, not as a public media file."""

    lookup_field = "uuid"

    def get(self, request, *args, **kwargs):
        recording = self.get_object()
        content_type = mimetypes.guess_type(recording.video.name)[0] or "application/octet-stream"

        return FileResponse(recording.video.open("rb"), content_type=content_type)


class RecordingThumbnailView(OwnRecordingsMixin, generics.GenericAPIView):
    """The preview image of one of the logged-in user's recordings."""

    lookup_field = "uuid"

    def get(self, request, *args, **kwargs):
        recording = self.get_object()
        if not recording.thumbnail:
            # TEMPORARY: recordings uploaded before previews existed get one the first time they are shown
            try:
                read_video(recording)
            except ValueError:
                raise Http404


        return FileResponse(recording.thumbnail.open("rb"), content_type="image/jpeg")


class PerformerListCreateView(generics.ListCreateAPIView):
    """The logged-in user's performers. POST adds one to their list."""

    permission_classes = [IsAuthenticated]
    serializer_class = PerformerSerializer

    def get_queryset(self):
        return Performer.objects.filter(owner=self.request.user).order_by("full_name")


class PerformerDetailView(generics.RetrieveUpdateAPIView):
    """One of the logged-in user's performers: view and edit. Anyone else's gets 'not found'."""

    permission_classes = [IsAuthenticated]
    serializer_class = PerformerSerializer

    def get_queryset(self):
        return Performer.objects.filter(owner=self.request.user)
