"""Admin configuration for clinicians app."""

from django.contrib import admin

from apps.clinicians.models import (
    Appointment,
    Clinician,
    ClinicianAvailability,
    ClinicianNote,
)


@admin.register(Clinician)
class ClinicianAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "specialty", "is_active", "created_at"]
    list_filter = ["role", "is_active", "hospitals"]
    search_fields = ["user__first_name", "user__last_name", "user__username"]
    filter_horizontal = ["hospitals"]


@admin.register(ClinicianNote)
class ClinicianNoteAdmin(admin.ModelAdmin):
    list_display = ["clinician", "patient", "note_type", "is_pinned", "created_at"]
    list_filter = ["note_type", "is_pinned"]
    search_fields = ["content"]
    raw_id_fields = ["patient", "clinician"]


@admin.register(ClinicianAvailability)
class ClinicianAvailabilityAdmin(admin.ModelAdmin):
    list_display = ["clinician", "day_of_week", "start_time", "end_time", "is_recurring"]
    list_filter = ["day_of_week", "is_recurring"]
    raw_id_fields = ["clinician"]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = [
        "patient",
        "clinician",
        "appointment_type",
        "status",
        "scheduled_start",
    ]
    list_filter = ["appointment_type", "status"]
    search_fields = [
        "patient__user__first_name",
        "patient__user__last_name",
        "notes",
    ]
    raw_id_fields = ["patient", "clinician", "created_by"]
