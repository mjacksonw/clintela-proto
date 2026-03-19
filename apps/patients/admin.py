"""Patient admin configuration."""

from django.contrib import admin
from django.utils.html import format_html

from apps.accounts.tokens import short_code_token_generator

from .models import Hospital, Patient


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    """Admin for Hospital model."""

    list_display = ("name", "code", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    """Admin for Patient model with auth URL generation."""

    list_display = (
        "get_full_name",
        "hospital",
        "leaflet_code",
        "status",
        "surgery_type",
        "get_days_post_op",
    )
    list_filter = ("status", "hospital", "surgery_type")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "leaflet_code",
        "mrn",
    )
    readonly_fields = ("get_auth_url", "get_days_post_op", "created_at", "updated_at")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "user",
                    "hospital",
                    "leaflet_code",
                    "date_of_birth",
                    "mrn",
                )
            },
        ),
        (
            "Surgery",
            {
                "fields": (
                    "surgery_type",
                    "surgery_date",
                    "discharge_date",
                    "get_days_post_op",
                )
            },
        ),
        (
            "Status",
            {
                "fields": ("status", "is_active"),
            },
        ),
        (
            "Authentication",
            {
                "fields": ("get_auth_url",),
                "description": "Click the URL below to test the auth flow for this patient.",
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Patient Name")
    def get_full_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description="Days Post-Op")
    def get_days_post_op(self, obj):
        days = obj.days_post_op()
        return f"{days} days" if days is not None else "—"

    @admin.display(description="Auth URL")
    def get_auth_url(self, obj):
        if not obj.pk:
            return "Save the patient first to generate an auth URL."
        token = short_code_token_generator.make_token(obj)
        code = short_code_token_generator.get_short_code(token)
        url = f"/accounts/start/?code={code}&token={token}&patient_id={obj.pk}"
        return format_html(
            '<a href="{}" target="_blank" style="font-size: 14px;">{}</a>',
            url,
            url,
        )
