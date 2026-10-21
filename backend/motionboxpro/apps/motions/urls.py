from django.urls import path

from . import views

urlpatterns = [
    path("motions/", views.MotionListCreateView.as_view(), name="motion_list"),
    path("motions/<uuid:uuid>/", views.MotionDetailView.as_view(), name="motion_detail"),
    path("motions/<uuid:motion_uuid>/recordings/", views.MotionRecordingsView.as_view(), name="motion_recordings"),
    path("motions/<uuid:motion_uuid>/projects/", views.MotionProjectCreateView.as_view(), name="motion_project_add"),
    path("motions/<uuid:motion_uuid>/versions/", views.StartRenderingView.as_view(), name="motion_version_start"),
    path(
        "motions/<uuid:motion_uuid>/versions/<int:number>/bvh/",
        views.MotionVersionBvhView.as_view(),
        name="motion_version_bvh",
    ),
]
