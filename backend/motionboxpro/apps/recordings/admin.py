from django.contrib import admin

from .models import Performer, Recording


@admin.register(Performer)
class PerformerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "owner", "email", "phone", "height_m")
    search_fields = ("full_name", "email")
    readonly_fields = ("created_at",)


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ("__str__", "owner", "performer", "lens_source", "created_at")
    list_filter = ("lens_source", "performer")
    search_fields = ("name",)
    readonly_fields = ("uuid", "created_at")
