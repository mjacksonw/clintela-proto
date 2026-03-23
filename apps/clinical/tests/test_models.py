"""Tests for clinical models."""

from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.clinical.constants import (
    ALERT_STATUS_ACTIVE,
    ALERT_TYPE_THRESHOLD,
    CONCEPT_HEART_RATE,
    SEVERITY_RED,
    TRAJECTORY_STABLE,
)
from apps.clinical.models import ClinicalAlert, ClinicalObservation, PatientClinicalSnapshot


@pytest.fixture
def hospital(db):
    from apps.patients.models import Hospital

    return Hospital.objects.create(name="Test Hospital", code="TEST01")


@pytest.fixture
def patient(db, hospital):
    import uuid

    from apps.accounts.models import User
    from apps.patients.models import Patient

    user = User.objects.create_user(
        username=f"test_{uuid.uuid4().hex[:8]}",
        password="testpass123",
        first_name="Test",
        last_name="Patient",
    )
    return Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1960-01-15",
        leaflet_code=uuid.uuid4().hex[:8],
        surgery_type="CABG",
    )


class TestClinicalObservation:
    def test_create_numeric_observation(self, patient):
        obs = ClinicalObservation.objects.create(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            concept_name="Heart Rate",
            value_numeric=Decimal("72.0"),
            unit="bpm",
            observed_at=timezone.now(),
            source="wearable",
        )
        assert obs.pk is not None
        assert obs.value_numeric == Decimal("72.0")
        assert obs.concept_id == CONCEPT_HEART_RATE
        assert not obs.is_anomalous

    def test_create_text_observation(self, patient):
        obs = ClinicalObservation.objects.create(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            concept_name="Heart Rate",
            value_text="Normal sinus rhythm",
            unit="",
            observed_at=timezone.now(),
            source="ehr",
        )
        assert obs.value_text == "Normal sinus rhythm"
        assert obs.value_numeric is None

    def test_str_representation(self, patient):
        obs = ClinicalObservation.objects.create(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            concept_name="Heart Rate",
            value_numeric=Decimal("72.0"),
            unit="bpm",
            observed_at=timezone.now(),
            source="wearable",
        )
        assert "Heart Rate" in str(obs)
        assert "72" in str(obs)

    def test_ordering_by_observed_at_desc(self, patient):
        now = timezone.now()
        ClinicalObservation.objects.create(  # older observation
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            concept_name="HR",
            value_numeric=70,
            unit="bpm",
            observed_at=now - timezone.timedelta(hours=1),
            source="wearable",
        )
        obs2 = ClinicalObservation.objects.create(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            concept_name="HR",
            value_numeric=75,
            unit="bpm",
            observed_at=now,
            source="wearable",
        )
        observations = list(ClinicalObservation.objects.filter(patient=patient))
        assert observations[0].pk == obs2.pk  # Most recent first

    def test_source_choices(self, patient):
        for source in ["wearable", "manual", "ehr", "patient_reported", "calculated"]:
            obs = ClinicalObservation.objects.create(
                patient=patient,
                concept_id=CONCEPT_HEART_RATE,
                concept_name="HR",
                value_numeric=72,
                unit="bpm",
                observed_at=timezone.now(),
                source=source,
            )
            assert obs.source == source


class TestPatientClinicalSnapshot:
    def test_create_snapshot(self, patient):
        snapshot = PatientClinicalSnapshot.objects.create(
            patient=patient,
            vital_signs={"hr": {"value": 72, "at": "2026-03-22T14:00:00Z"}},
            risk_score=Decimal("15.00"),
            trajectory=TRAJECTORY_STABLE,
            active_alerts_count=0,
            data_completeness=Decimal("0.75"),
        )
        assert snapshot.patient == patient
        assert snapshot.trajectory == TRAJECTORY_STABLE

    def test_one_to_one_constraint(self, patient):
        PatientClinicalSnapshot.objects.create(
            patient=patient,
            trajectory=TRAJECTORY_STABLE,
        )
        with pytest.raises(IntegrityError):
            PatientClinicalSnapshot.objects.create(
                patient=patient,
                trajectory=TRAJECTORY_STABLE,
            )

    def test_str_representation(self, patient):
        snapshot = PatientClinicalSnapshot.objects.create(
            patient=patient,
            trajectory="improving",
            risk_score=Decimal("25"),
        )
        assert "improving" in str(snapshot)


class TestClinicalAlert:
    def test_create_alert(self, patient):
        alert = ClinicalAlert.objects.create(
            patient=patient,
            alert_type=ALERT_TYPE_THRESHOLD,
            severity=SEVERITY_RED,
            rule_name="hr_critical",
            title="Critical Heart Rate",
            description="HR > 120 bpm",
            rule_rationale="Heart rate measured at 125 bpm (threshold: >120 bpm).",
        )
        assert alert.pk is not None
        assert alert.status == ALERT_STATUS_ACTIVE
        assert alert.rule_rationale  # FDA transparency field

    def test_unique_active_alert_per_rule(self, patient):
        ClinicalAlert.objects.create(
            patient=patient,
            alert_type=ALERT_TYPE_THRESHOLD,
            severity=SEVERITY_RED,
            rule_name="hr_critical",
            title="Alert 1",
            description="First",
        )
        with pytest.raises(IntegrityError):
            ClinicalAlert.objects.create(
                patient=patient,
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_RED,
                rule_name="hr_critical",
                title="Alert 2",
                description="Second",
            )

    def test_can_create_same_rule_after_resolve(self, patient):
        alert1 = ClinicalAlert.objects.create(
            patient=patient,
            alert_type=ALERT_TYPE_THRESHOLD,
            severity=SEVERITY_RED,
            rule_name="hr_critical",
            title="Alert 1",
            description="First",
        )
        alert1.status = "resolved"
        alert1.save()

        # Should succeed — resolved alert doesn't block new active alert
        alert2 = ClinicalAlert.objects.create(
            patient=patient,
            alert_type=ALERT_TYPE_THRESHOLD,
            severity=SEVERITY_RED,
            rule_name="hr_critical",
            title="Alert 2",
            description="Second",
        )
        assert alert2.pk is not None

    def test_str_representation(self, patient):
        alert = ClinicalAlert.objects.create(
            patient=patient,
            alert_type=ALERT_TYPE_THRESHOLD,
            severity=SEVERITY_RED,
            rule_name="test",
            title="Test Alert",
            description="Test",
        )
        assert "RED" in str(alert)
        assert "Test Alert" in str(alert)
