"""Accounts app - User authentication and management."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom User model for Clintela."""

    ROLE_CHOICES = [
        ("patient", "Patient"),
        ("clinician", "Clinician"),
        ("caregiver", "Caregiver"),
        ("admin", "Administrator"),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="patient",
    )
    phone_number = models.CharField(max_length=20, blank=True, db_index=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_user"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class AuthAttempt(models.Model):
    """Audit log for patient authentication attempts."""

    METHOD_CHOICES = [
        ("sms_link", "SMS Link"),
        ("manual", "Manual Entry"),
        ("magic_link", "Magic Link"),
    ]

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="auth_attempts",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    success = models.BooleanField()
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    failure_reason = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "accounts_auth_attempt"
        ordering = ["-timestamp"]

    def __str__(self):
        status = "success" if self.success else "failed"
        return f"Auth {status} for {self.patient} at {self.timestamp}"
