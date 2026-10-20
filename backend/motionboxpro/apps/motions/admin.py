from django.contrib import admin

from .models import Motion, MotionRecording, MotionVersion


class MotionRecordingInline(admin.TabularInline):
    model = MotionRecording
    extra = 0
    readonly_fields = ("uuid",)


class MotionVersionInline(admin.TabularInline):
    model = MotionVersion
    extra = 0
    readonly_fields = ("uuid", "created_at", "updated_at")


@admin.register(Motion)
class MotionAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "status", "recording_count", "updated_at")
    search_fields = ("name",)
    readonly_fields = ("uuid", "created_at", "updated_at", "status", "last_updated", "recording_count")
    inlines = [MotionRecordingInline, MotionVersionInline]


@admin.register(MotionVersion)
class MotionVersionAdmin(admin.ModelAdmin):
    list_display = ("motion", "number", "source", "status", "parent", "created_at")
    list_filter = ("source", "status")
    search_fields = ("motion__name", "label")
    readonly_fields = ("uuid", "created_at", "updated_at")


@admin.register(MotionRecording)
class MotionRecordingAdmin(admin.ModelAdmin):
    list_display = ("motion", "recording", "camera_slot", "clap_time_s", "reprojection_error_px")
    list_filter = ("camera_slot",)
    readonly_fields = ("uuid",)
