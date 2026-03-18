"""Clinicians app - Healthcare provider management."""

from django.db import models


class Clinician(models.Model):
    """Healthcare provider/clinician."""

    ROLE_CHOICES = [
        ("physician", "Physician"),
        ("nurse", "Nurse"),
        ("pa", "Physician Assistant"),
        ("np", "Nurse Practitioner"),
        ("coordinator", "Care Coordinator"),
    ]

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="clinician_profile",
    )
    hospitals = models.ManyToManyField(
        "patients.Hospital",
        related_name="clinicians",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    specialty = models.CharField(max_length=100, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    npi_number = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clinicians_clinician"

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_display()})"
