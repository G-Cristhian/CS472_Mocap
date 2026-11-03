from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Motion, MotionVersion
from .rendering import start_render
from .serializers import (
    MotionProjectAddSerializer,
    MotionRecordingsSetSerializer,
    MotionSerializer,
    StartRenderingSerializer,
)


class OwnMotionsMixin:
    """Only logged-in users, and only their own motions. Anyone else gets 'not found'."""

    permission_classes = [IsAuthenticated]
    serializer_class = MotionSerializer

    def get_queryset(self):
        return Motion.objects.filter(owner=self.request.user).order_by("-created_at")


class MotionListCreateView(OwnMotionsMixin, generics.ListCreateAPIView):
    """GET: the logged-in user's motions, newest first. POST: create a motion, optionally in one of their projects."""


class MotionDetailView(OwnMotionsMixin, generics.RetrieveAPIView):
    """GET one of the logged-in user's motions, with its projects, cameras, performers and versions."""

    lookup_field = "uuid"


class OneMotionMixin:
    """An action on one of the logged-in user's motions, named by the motion's uuid in the URL."""

    permission_classes = [IsAuthenticated]

    def get_motion(self):
        return get_object_or_404(Motion, uuid=self.kwargs["motion_uuid"], owner=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["motion"] = self.get_motion()

        return context


class MotionRecordingsView(OneMotionMixin, generics.GenericAPIView):
    """PUT: set the recordings the motion uses, two to four. Returns the motion."""

    serializer_class = MotionRecordingsSetSerializer

    def put(self, request, *args, **kwargs):
        motion = self.get_motion()
        serializer = self.get_serializer(motion, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(MotionSerializer(motion, context={"request": request}).data)


class MotionProjectCreateView(OneMotionMixin, generics.CreateAPIView):
    """POST: put the motion into one of the logged-in user's projects. A motion can be in several."""

    serializer_class = MotionProjectAddSerializer


class StartRenderingView(OneMotionMixin, APIView):
    """
    POST: render the motion as a new version, in the background. Answers at once with the
    motion; the new version's status says how the render is going.
    """

    def post(self, request, motion_uuid):
        motion = self.get_motion()
        serializer = StartRenderingSerializer(data=request.data, context={"request": request, "motion": motion})
        serializer.is_valid(raise_exception=True)
        version = serializer.save()
        # the render starts only once the version is in the database
        transaction.on_commit(lambda: start_render(version.pk))

        return Response(MotionSerializer(motion, context={"request": request}).data, status=202)


class MotionVersionBvhView(OneMotionMixin, APIView):
    """GET: the skeleton animation (.bvh) of one finished version of the motion, as text."""

    def get(self, request, motion_uuid, number):
        version = get_object_or_404(MotionVersion, motion=self.get_motion(), number=number)
        if version.status != MotionVersion.Status.DONE:
            raise NotFound("This version has no skeleton yet.")

        return HttpResponse(version.bvh, content_type="text/plain; charset=utf-8")
