"""Caregivers app - Family/caregiver access."""

from django.db import models


class Caregiver(models.Model):
    """Family member or caregiver with patient access."""

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="caregiver_profile",
    )
    patients = models.ManyToManyField(
        "patients.Patient",
        related_name="caregivers",
        through="CaregiverRelationship",
    )
    relationship_type = models.CharField(max_length=50, blank=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "caregivers_caregiver"

    def __str__(self):
        return f"{self.user.get_full_name()} (Caregiver)"


class CaregiverRelationship(models.Model):
    """Link between caregiver and patient."""
    caregiver = models.ForeignKey(Caregiver, on_delete=models.CASCADE)
    patient = models.ForeignKey("patients.Patient", on_delete=models.CASCADE)
    relationship = models.CharField(max_length=50)
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "caregivers_relationship"
        unique_together = ["caregiver", "patient"]

    def __str__(self):
        return self.relationship
