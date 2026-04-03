"""Notifications app - Alerts and escalations.

Model hierarchy:
    Notification (intent to notify)
    ├── NotificationDelivery (per-channel delivery attempt)
    │   status: pending → sent → delivered
    │                  └→ failed / bounced
    ├── DeviceToken (push notification token per device)
    │   platform: ios / android
    │   lifecycle: active → deactivated (on 410/gone or logout)
    └── NotificationPreference (patient channel preferences)
        controls which channels + quiet hours
"""

from django.db import models


class DeviceToken(models.Model):
    """Push notification token for a patient's device.

    Each physical device (phone/tablet) registers one token via FCM.
    A patient can have multiple active tokens (multiple devices).
    Tokens are deactivated on APNs 410/gone, logout, or uninstall.
    """

    PLATFORM_CHOICES = [
        ("ios", "iOS"),
        ("android", "Android"),
    ]

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="device_tokens",
    )
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    token = models.CharField(
        max_length=255,
        unique=True,
        help_text="FCM registration token",
    )
    device_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. iPhone 15, Pixel 8",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_device_token"
        indexes = [
            models.Index(
                fields=["patient", "is_active"],
                name="idx_device_patient_active",
            ),
        ]

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.patient} - {self.platform} ({status})"


class Notification(models.Model):
    """System notification/alert — represents the intent to notify.

    Each Notification spawns one or more NotificationDelivery records
    (one per channel). Delivery status lives on NotificationDelivery,
    not here.
    """

    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("critical", "Critical"),
    ]

    TYPE_CHOICES = [
        ("escalation", "Escalation"),
        ("reminder", "Reminder"),
        ("alert", "Alert"),
        ("update", "Update"),
        ("celebration", "Celebration"),
    ]

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    clinician = models.ForeignKey(
        "clinicians.Clinician",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.severity} - {self.title}"


class NotificationDelivery(models.Model):
    """Per-channel delivery attempt for a Notification.

    Tracks the lifecycle of delivering a notification through a specific
    channel (in_app, sms, email). Each Notification can have multiple
    deliveries — one per channel.
    """

    CHANNEL_CHOICES = [
        ("in_app", "In-App"),
        ("push", "Push"),
        ("sms", "SMS"),
        ("email", "Email"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
        ("bounced", "Bounced"),
    ]

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    device = models.ForeignKey(
        DeviceToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
        help_text="Set for push deliveries (one delivery per device token)",
    )
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    delivered_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    external_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="External reference (e.g. Twilio SID) for status correlation",
    )
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_delivery"
        indexes = [
            models.Index(
                fields=["notification", "channel"],
                name="idx_delivery_notif_channel",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="idx_delivery_status_created",
            ),
        ]
        verbose_name_plural = "notification deliveries"

    def __str__(self):
        return f"{self.channel} delivery for notification #{self.notification_id} ({self.status})"


class NotificationPreference(models.Model):
    """Patient preference for a specific notification channel + type.

    Controls whether a patient receives notifications of a given type
    through a given channel, and optionally defines quiet hours during
    which delivery is deferred.
    """

    CHANNEL_CHOICES = NotificationDelivery.CHANNEL_CHOICES

    TYPE_CHOICES = Notification.TYPE_CHOICES

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    enabled = models.BooleanField(default=True)
    quiet_hours_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Start of quiet hours (notifications deferred, not dropped)",
    )
    quiet_hours_end = models.TimeField(
        null=True,
        blank=True,
        help_text="End of quiet hours",
    )

    class Meta:
        db_table = "notifications_preference"
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "channel", "notification_type"],
                name="uniq_patient_channel_type",
            ),
        ]

    def __str__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"{self.patient} - {self.channel}/{self.notification_type} ({status})"
