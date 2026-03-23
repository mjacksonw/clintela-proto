"""Clinical Intelligence models.

Three-layer architecture for patient clinical state:
  1. ClinicalObservation — time-series data points (OMOP concept IDs)
  2. PatientClinicalSnapshot — computed current state (the "kernel")
  3. ClinicalAlert — rules-based detection with FDA-aligned transparency

Architecture diagram:
  Observations (time-series) ──► Snapshot (computed state) ──► Alerts (rules-based)
       │                              │                            │
       ▼                              ▼                            ▼
  OMOP concept IDs              trajectory + risk_score      rule_rationale
  source attribution            vital_signs (JSON)           auto-triage
"""

import uuid

from django.db import models

from apps.clinical.constants import (
    ALERT_STATUS_ACTIVE,
    ALERT_STATUS_CHOICES,
    ALERT_TYPE_CHOICES,
    QUALITY_CHOICES,
    SEVERITY_CHOICES,
    SOURCE_CHOICES,
    TRAJECTORY_CHOICES,
    TRAJECTORY_STABLE,
)


class ClinicalObservation(models.Model):
    """A single clinical measurement at a point in time.

    Uses OMOP concept IDs so data maps directly when the real
    Epic→OMOP pipeline connects. Each row is one observation
    (e.g., heart rate = 72 bpm at 2026-03-22 14:30).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="clinical_observations",
    )
    concept_id = models.IntegerField(
        db_index=True,
        help_text="OMOP concept ID (e.g., 3027018 = Heart Rate)",
    )
    concept_name = models.CharField(
        max_length=100,
        help_text="Human-readable name",
    )
    value_numeric = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    value_text = models.CharField(
        max_length=500,
        blank=True,
        help_text="For non-numeric observations",
    )
    unit = models.CharField(max_length=20)
    observed_at = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_device = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g., Apple Watch, Withings Scale",
    )
    quality = models.CharField(
        max_length=20,
        choices=QUALITY_CHOICES,
        default="verified",
    )
    metadata = models.JSONField(default=dict, blank=True)
    is_anomalous = models.BooleanField(
        default=False,
        help_text="Flagged by rules engine",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clinical_observation"
        ordering = ["-observed_at"]
        indexes = [
            models.Index(
                fields=["patient", "concept_id", "observed_at"],
                name="idx_obs_patient_concept_time",
            ),
            models.Index(
                fields=["patient", "observed_at"],
                name="idx_obs_patient_time",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(value_numeric__isnull=True, value_text=""),
                name="obs_value_not_empty",
            ),
        ]

    def __str__(self):
        val = self.value_numeric if self.value_numeric is not None else self.value_text
        return f"{self.concept_name}: {val} {self.unit} @ {self.observed_at:%Y-%m-%d %H:%M}"


class PatientClinicalSnapshot(models.Model):
    """Computed current clinical state for a patient.

    Recomputed on each observation ingest and nightly by Celery.
    This is the "kernel" — the single source of truth for
    "how is this patient doing right now?"
    """

    patient = models.OneToOneField(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="clinical_snapshot",
    )
    computed_at = models.DateTimeField(auto_now=True)
    vital_signs = models.JSONField(
        default=dict,
        blank=True,
        help_text='Latest values: {"hr": {"value": 72, "at": "...", "trend": "stable"}, ...}',
    )
    risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Composite 0-100 risk score",
    )
    risk_factors = models.JSONField(
        default=list,
        blank=True,
        help_text="Contributing factors with weights",
    )
    trajectory = models.CharField(
        max_length=20,
        choices=TRAJECTORY_CHOICES,
        default=TRAJECTORY_STABLE,
    )
    active_alerts_count = models.IntegerField(
        default=0,
        help_text="Denormalized count of unresolved alerts",
    )
    last_ehr_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When EHR data was last pulled (future)",
    )
    data_completeness = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        help_text="0.0-1.0, how much data we have vs. expected",
    )

    class Meta:
        db_table = "clinical_snapshot"

    def __str__(self):
        return f"{self.patient}: {self.trajectory} (risk {self.risk_score})"


class ClinicalAlert(models.Model):
    """Rules-based clinical alert with FDA-aligned transparency.

    Each alert stores the rule_rationale — a plain-language explanation
    of why the rule fired, per FDA 2026 CDS guidance requiring:
    - Plain-language algorithmic logic
    - Input data source identification
    - Disclosure of clinical evidence
    - Contextual patient-specific factors
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="clinical_alerts",
    )
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    rule_name = models.CharField(
        max_length=100,
        help_text="Identifier of the rule that fired (e.g., weight_gain_3day)",
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    rule_rationale = models.TextField(
        blank=True,
        help_text="FDA-aligned plain-language explanation of why this alert fired",
    )
    trigger_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="The observations that triggered this alert",
    )
    status = models.CharField(
        max_length=20,
        choices=ALERT_STATUS_CHOICES,
        default=ALERT_STATUS_ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_clinical_alerts",
    )
    resolved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_clinical_alerts",
    )
    escalation = models.ForeignKey(
        "agents.Escalation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clinical_alerts",
    )
    auto_action_taken = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., messaged_patient, notified_clinician",
    )

    class Meta:
        db_table = "clinical_alert"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["patient", "status"],
                name="idx_alert_patient_status",
            ),
            models.Index(
                fields=["patient", "rule_name", "status"],
                name="idx_alert_patient_rule_status",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "rule_name"],
                condition=models.Q(status=ALERT_STATUS_ACTIVE),
                name="unique_active_alert_per_rule",
            ),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title} — {self.patient}"
