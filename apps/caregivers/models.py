"""Caregivers app - Family/caregiver access."""

import secrets
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone


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
    is_active = models.BooleanField(default=True)
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "caregivers_relationship"
        unique_together = ["caregiver", "patient"]

    def __str__(self):
        return self.relationship


def _generate_invitation_token():
    return secrets.token_urlsafe(32)


def _default_expiry():
    return timezone.now() + timedelta(days=7)


class CaregiverInvitation(models.Model):
    """Invitation for a caregiver to connect with a patient.

    Flow:
    1. Patient creates invitation (pending)
    2. System sends invite link via SMS/email
    3. Caregiver clicks link, verifies with patient's leaflet code
    4. Patient confirms → caregiver gets read-only access
    5. Patient can revoke access at any time
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]

    RELATIONSHIP_CHOICES = [
        ("spouse", "Spouse"),
        ("child", "Child"),
        ("parent", "Parent"),
        ("sibling", "Sibling"),
        ("friend", "Friend"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="caregiver_invitations",
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=_generate_invitation_token,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    expires_at = models.DateTimeField(default=_default_expiry)
    accepted_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_invitations",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "caregivers_invitation"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["patient", "status"],
                name="idx_invitation_patient_status",
            ),
            models.Index(fields=["token"], name="idx_invitation_token"),
        ]

    def __str__(self):
        return f"Invitation for {self.name} ({self.status})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_acceptable(self):
        """Can this invitation still be accepted?"""
        return self.status == "pending" and not self.is_expired

    def accept(self, user, leaflet_code: str) -> CaregiverRelationship:
        """Accept invitation after leaflet code verification.

        Args:
            user: The caregiver's User account.
            leaflet_code: Patient's leaflet code for verification.

        Returns:
            The created CaregiverRelationship.

        Raises:
            InvalidInvitationError: If the invitation cannot be accepted.
            LeafletCodeMismatchError: If the leaflet code doesn't match.
        """
        if not self.is_acceptable:
            if self.is_expired:
                self.status = "expired"
                self.save(update_fields=["status"])
            raise InvalidInvitationError(f"Invitation is {self.status}, cannot accept.")

        if leaflet_code != self.patient.leaflet_code:
            raise LeafletCodeMismatchError("Invalid verification code.")

        now = timezone.now()

        # Create or get caregiver profile
        caregiver, _ = Caregiver.objects.get_or_create(
            user=user,
            defaults={"is_verified": True, "is_active": True},
        )

        # Create relationship
        rel, created = CaregiverRelationship.objects.get_or_create(
            caregiver=caregiver,
            patient=self.patient,
            defaults={
                "relationship": self.relationship,
                "accepted_at": now,
            },
        )
        if not created:
            rel.relationship = self.relationship
            rel.accepted_at = now
            rel.is_active = True
            rel.save(update_fields=["relationship", "accepted_at", "is_active"])

        # Mark invitation accepted
        self.status = "accepted"
        self.accepted_by = user
        self.accepted_at = now
        self.save(update_fields=["status", "accepted_by", "accepted_at"])

        return rel

    def revoke(self):
        """Revoke this invitation."""
        if self.status not in ("pending", "accepted"):
            raise InvalidInvitationError(f"Cannot revoke invitation with status '{self.status}'.")
        self.status = "revoked"
        self.revoked_at = timezone.now()
        self.save(update_fields=["status", "revoked_at"])


class InvalidInvitationError(Exception):
    """Raised when an invitation operation is not allowed."""


class LeafletCodeMismatchError(Exception):
    """Raised when the leaflet code doesn't match during acceptance."""
