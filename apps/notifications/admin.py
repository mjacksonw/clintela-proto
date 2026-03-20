from django.contrib import admin

from .models import Notification, NotificationDelivery, NotificationPreference


class NotificationDeliveryInline(admin.TabularInline):
    model = NotificationDelivery
    extra = 0
    readonly_fields = ("created_at", "delivered_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "notification_type", "severity", "patient", "clinician", "is_read", "created_at")
    list_filter = ("notification_type", "severity", "is_read")
    search_fields = ("title", "message")
    readonly_fields = ("created_at",)
    inlines = [NotificationDeliveryInline]


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("notification", "channel", "status", "retry_count", "created_at", "delivered_at")
    list_filter = ("channel", "status")
    search_fields = ("external_id",)
    readonly_fields = ("created_at",)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("patient", "channel", "notification_type", "enabled", "quiet_hours_start", "quiet_hours_end")
    list_filter = ("channel", "notification_type", "enabled")
