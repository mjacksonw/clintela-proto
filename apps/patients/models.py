"""Patients app - Patient management and records."""

from django.db import models


class Hospital(models.Model):
    """Hospital/Healthcare organization."""
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "patients_hospital"

    def __str__(self):
        return self.name


class Patient(models.Model):
    """Patient record."""

    STATUS_CHOICES = [
        ("green", "Green - Stable"),
        ("yellow", "Yellow - Needs Attention"),
        ("orange", "Orange - Escalated"),
        ("red", "Red - Critical"),
    ]

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.SET_NULL,
        null=True,
        related_name="patients",
    )
    date_of_birth = models.DateField()
    mrn = models.CharField(  # Medical Record Number
        max_length=50,
        blank=True,
        verbose_name="Medical Record Number",
    )
    leaflet_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique code for patient access",
    )
    surgery_type = models.CharField(max_length=100, blank=True)
    surgery_date = models.DateField(null=True, blank=True)
    discharge_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="green",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patients_patient"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.leaflet_code})"

    def days_post_op(self):
        """Calculate days since surgery."""
        from datetime import date
        if self.surgery_date:
            return (date.today() - self.surgery_date).days
        return None
