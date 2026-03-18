"""Notifications app - Alerts and escalations."""

from django.db import models


class Notification(models.Model):
    """System notification/alert."""

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
