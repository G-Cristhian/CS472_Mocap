from django.urls import path

from . import views

urlpatterns = [
    path("recordings/", views.RecordingListCreateView.as_view(), name="recording_list"),
    path("recordings/<uuid:uuid>/", views.RecordingDetailView.as_view(), name="recording_detail"),
    path("recordings/<uuid:uuid>/video/", views.RecordingVideoView.as_view(), name="recording_video"),
    path("recordings/<uuid:uuid>/thumbnail/", views.RecordingThumbnailView.as_view(), name="recording_thumbnail"),
    path("performers/", views.PerformerListCreateView.as_view(), name="performer_list"),
    path("performers/<int:pk>/", views.PerformerDetailView.as_view(), name="performer_detail"),
]
