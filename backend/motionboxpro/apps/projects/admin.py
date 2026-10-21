from django.contrib import admin

from .models import Project, ProjectMotion


class ProjectMotionInline(admin.TabularInline):
    model = ProjectMotion
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "owner", "updated_at")
    list_filter = ("category",)
    search_fields = ("name", "category")
    readonly_fields = ("uuid", "created_at", "updated_at")
    inlines = [ProjectMotionInline]


@admin.register(ProjectMotion)
class ProjectMotionAdmin(admin.ModelAdmin):
    list_display = ("motion", "project", "order", "added_at")
    list_filter = ("project",)
    ordering = ("project", "order")
