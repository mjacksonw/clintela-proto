"""Patients app - Patient management and records."""

import uuid

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

    # Lifecycle status tracks the patient's journey through the care system
    #
    # pre_surgery → admitted → in_surgery → post_op → discharged → recovering → recovered
    #                                                                    ↓
    #                                                               readmitted → admitted
    LIFECYCLE_CHOICES = [
        ("pre_surgery", "Pre-Surgery"),
        ("admitted", "Admitted"),
        ("in_surgery", "In Surgery"),
        ("post_op", "Post-Op"),
        ("discharged", "Discharged"),
        ("recovering", "Recovering"),
        ("recovered", "Recovered"),
        ("readmitted", "Readmitted"),
    ]

    # Valid lifecycle transitions: {from_status: [allowed_to_statuses]}
    LIFECYCLE_TRANSITIONS = {
        "pre_surgery": ["admitted"],
        "admitted": ["in_surgery"],
        "in_surgery": ["post_op"],
        "post_op": ["discharged"],
        "discharged": ["recovering"],
        "recovering": ["recovered", "readmitted"],
        "recovered": [],  # Terminal state
        "readmitted": ["admitted"],
    }

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
    lifecycle_status = models.CharField(
        max_length=20,
        choices=LIFECYCLE_CHOICES,
        default="pre_surgery",
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

    def transition_lifecycle(
        self, new_status: str, triggered_by: str = "", reason: str = ""
    ) -> "PatientStatusTransition":
        """Transition lifecycle status with validation and audit trail.

        Args:
            new_status: Target lifecycle status.
            triggered_by: Who/what triggered this (e.g., "system", "clinician:jane").
            reason: Human-readable reason for the transition.

        Returns:
            The created PatientStatusTransition record.

        Raises:
            InvalidLifecycleTransitionError: If the transition is not allowed.
        """
        allowed = self.LIFECYCLE_TRANSITIONS.get(self.lifecycle_status, [])
        if new_status not in allowed:
            raise InvalidLifecycleTransitionError(
                f"Cannot transition from '{self.lifecycle_status}' to '{new_status}'. " f"Allowed: {allowed}"
            )

        old_status = self.lifecycle_status
        self.lifecycle_status = new_status
        self.save(update_fields=["lifecycle_status", "updated_at"])

        return PatientStatusTransition.objects.create(
            patient=self,
            from_status=old_status,
            to_status=new_status,
            triggered_by=triggered_by,
            reason=reason,
        )


class InvalidLifecycleTransitionError(Exception):
    """Raised when a lifecycle status transition is not allowed."""


class PatientStatusTransition(models.Model):
    """Audit trail for patient lifecycle status changes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="lifecycle_transitions",
    )
    from_status = models.CharField(max_length=20, choices=Patient.LIFECYCLE_CHOICES)
    to_status = models.CharField(max_length=20, choices=Patient.LIFECYCLE_CHOICES)
    triggered_by = models.CharField(
        max_length=100,
        blank=True,
        help_text="Who/what triggered this transition",
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "patients_status_transition"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["patient", "created_at"],
                name="idx_transition_patient_created",
            ),
        ]

    def __str__(self):
        return f"{self.patient}: {self.from_status} → {self.to_status}"


class ConsentRecord(models.Model):
    """Track patient consent for data sharing and communications.

    Each record represents a single consent grant or revocation.
    Check the most recent record per (patient, consent_type) to
    determine current consent status.
    """

    CONSENT_TYPE_CHOICES = [
        ("data_sharing_caregiver", "Data Sharing with Caregivers"),
        ("data_sharing_research", "Data Sharing for Research"),
        ("communication_sms", "SMS Communication"),
        ("communication_email", "Email Communication"),
        ("ai_interaction", "AI-Powered Care Assistance"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="consent_records",
    )
    consent_type = models.CharField(
        max_length=30,
        choices=CONSENT_TYPE_CHOICES,
    )
    granted = models.BooleanField()
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    granted_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consent_grants",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "patients_consent_record"
        ordering = ["-granted_at"]
        indexes = [
            models.Index(
                fields=["patient", "consent_type", "granted_at"],
                name="idx_consent_patient_type_at",
            ),
        ]

    def __str__(self):
        action = "granted" if self.granted else "revoked"
        return f"{self.patient}: {self.consent_type} {action}"

    @classmethod
    def has_consent(cls, patient, consent_type: str) -> bool:
        """Check if a patient currently has active consent of the given type."""
        latest = (
            cls.objects.filter(
                patient=patient,
                consent_type=consent_type,
            )
            .order_by("-granted_at")
            .first()
        )
        return latest.granted if latest else False
