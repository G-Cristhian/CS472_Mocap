from django.urls import path

from . import views

urlpatterns = [
    path("projects/", views.ProjectListCreateView.as_view(), name="project_list"),
]
