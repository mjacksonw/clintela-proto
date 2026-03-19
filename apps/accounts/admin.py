"""Accounts admin configuration."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuthAttempt, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin for custom User model."""

    list_display = (
        "username",
        "first_name",
        "last_name",
        "role",
        "phone_number",
        "is_active",
    )
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email", "phone_number")

    # Add custom fields to the existing UserAdmin fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Clintela",
            {
                "fields": ("role", "phone_number", "email_verified"),
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Clintela",
            {
                "fields": ("role", "first_name", "last_name", "phone_number"),
            },
        ),
    )


@admin.register(AuthAttempt)
class AuthAttemptAdmin(admin.ModelAdmin):
    """Admin for AuthAttempt model (read-only audit log)."""

    list_display = ("patient", "success", "method", "timestamp")
    list_filter = ("success", "method")
    search_fields = ("patient__user__first_name", "patient__user__last_name")
    readonly_fields = (
        "patient",
        "timestamp",
        "ip_address",
        "user_agent",
        "success",
        "method",
        "failure_reason",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
