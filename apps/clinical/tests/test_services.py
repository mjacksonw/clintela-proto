"""Tests for clinical data service."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.clinical.constants import (
    CONCEPT_BODY_WEIGHT,
    CONCEPT_HEART_RATE,
    TRAJECTORY_DETERIORATING,
    TRAJECTORY_STABLE,
)
from apps.clinical.models import ClinicalAlert, PatientClinicalSnapshot
from apps.clinical.services import ClinicalDataService


@pytest.fixture
def hospital(db):
    from apps.patients.models import Hospital

    return Hospital.objects.create(name="Test Hospital", code="SVC01")


@pytest.fixture
def patient(db, hospital):
    import uuid

    from apps.accounts.models import User
    from apps.patients.models import Patient

    user = User.objects.create_user(
        username=f"svc_{uuid.uuid4().hex[:8]}",
        password="testpass123",  # pragma: allowlist secret
        first_name="Service",
        last_name="Test",
    )
    return Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1960-01-15",
        leaflet_code=uuid.uuid4().hex[:8],
        surgery_type="CABG",
    )


class TestIngestObservation:
    def test_ingest_valid_observation(self, patient):
        obs = ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            source="wearable",
            source_device="Apple Watch",
        )
        assert obs.pk is not None
        assert obs.concept_name == "Heart Rate"
        assert obs.unit == "bpm"
        assert obs.value_numeric == Decimal("72")

    def test_ingest_invalid_concept_id(self, patient):
        with pytest.raises(ValueError, match="Invalid concept_id"):
            ClinicalDataService.ingest_observation(
                patient=patient,
                concept_id=99999,
                value_numeric=72,
            )

    def test_ingest_with_skip_processing(self, patient, settings):
        settings.ENABLE_CLINICAL_DATA = True
        obs = ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            skip_processing=True,
        )
        assert obs.pk is not None
        # No snapshot should be created (skip_processing=True)
        assert not PatientClinicalSnapshot.objects.filter(patient=patient).exists()

    def test_ingest_auto_sets_concept_name_and_unit(self, patient):
        obs = ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_BODY_WEIGHT,
            value_numeric=185,
        )
        assert obs.concept_name == "Body Weight"
        assert obs.unit == "lbs"

    def test_ingest_custom_observed_at(self, patient):
        custom_time = timezone.now() - timedelta(hours=6)
        obs = ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            observed_at=custom_time,
        )
        assert obs.observed_at == custom_time


class TestComputeSnapshot:
    def test_compute_with_no_data(self, patient):
        snapshot = ClinicalDataService.compute_snapshot(patient)
        assert snapshot.trajectory == TRAJECTORY_STABLE
        # Risk score is 10 when data_completeness < 0.5 (no data = 0.0 completeness)
        assert snapshot.risk_score == Decimal("10")
        assert snapshot.active_alerts_count == 0

    def test_compute_with_observations(self, patient):
        now = timezone.now()
        for i in range(5):
            ClinicalDataService.ingest_observation(
                patient=patient,
                concept_id=CONCEPT_HEART_RATE,
                value_numeric=72 + i,
                observed_at=now - timedelta(days=i),
                skip_processing=True,
            )
        snapshot = ClinicalDataService.compute_snapshot(patient)
        assert snapshot.vital_signs.get("Heart Rate") is not None
        assert snapshot.data_completeness >= Decimal("0")

    def test_snapshot_update_or_create(self, patient):
        """Should update existing snapshot, not create a new one."""
        snap1 = ClinicalDataService.compute_snapshot(patient)
        snap2 = ClinicalDataService.compute_snapshot(patient)
        assert snap1.pk == snap2.pk
        assert PatientClinicalSnapshot.objects.filter(patient=patient).count() == 1


class TestUpdateTriageColor:
    def test_red_alert_sets_red_triage(self, patient):
        ClinicalAlert.objects.create(
            patient=patient,
            alert_type="threshold",
            severity="red",
            rule_name="test_red",
            title="Test",
            description="Test",
        )
        ClinicalDataService.update_triage_color(patient)
        patient.refresh_from_db()
        assert patient.status == "red"

    def test_no_alerts_resets_to_green(self, patient):
        patient.status = "orange"
        patient.save()
        ClinicalDataService.update_triage_color(patient)
        patient.refresh_from_db()
        assert patient.status == "green"

    def test_resolved_alert_doesnt_affect_triage(self, patient):
        alert = ClinicalAlert.objects.create(
            patient=patient,
            alert_type="threshold",
            severity="red",
            rule_name="test_resolved",
            title="Test",
            description="Test",
        )
        alert.status = "resolved"
        alert.save()
        ClinicalDataService.update_triage_color(patient)
        patient.refresh_from_db()
        assert patient.status == "green"

    def test_orange_severity_sets_orange_triage(self, patient):
        ClinicalAlert.objects.create(
            patient=patient,
            alert_type="threshold",
            severity="orange",
            rule_name="test_orange",
            title="Test",
            description="Test",
        )
        ClinicalDataService.update_triage_color(patient)
        patient.refresh_from_db()
        assert patient.status == "orange"


class TestGetLatestVitals:
    def test_returns_latest_per_vital(self, patient):
        now = timezone.now()
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=70,
            observed_at=now - timedelta(hours=2),
            skip_processing=True,
        )
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=75,
            observed_at=now,
            skip_processing=True,
        )
        vitals = ClinicalDataService.get_latest_vitals(patient)
        assert vitals["Heart Rate"]["value"] == 75.0

    def test_empty_when_no_data(self, patient):
        vitals = ClinicalDataService.get_latest_vitals(patient)
        assert vitals == {}


class TestGetTrendData:
    def test_returns_chronological_data(self, patient):
        now = timezone.now()
        for i in range(5):
            ClinicalDataService.ingest_observation(
                patient=patient,
                concept_id=CONCEPT_HEART_RATE,
                value_numeric=70 + i,
                observed_at=now - timedelta(days=4 - i),
                skip_processing=True,
            )
        trend = ClinicalDataService.get_trend_data(patient, CONCEPT_HEART_RATE, days=7)
        assert len(trend) == 5
        values = [float(t["value_numeric"]) for t in trend]
        assert values == [70.0, 71.0, 72.0, 73.0, 74.0]


class TestGetPatientAlerts:
    def test_returns_alerts(self, patient):
        ClinicalAlert.objects.create(
            patient=patient,
            alert_type="threshold",
            severity="red",
            rule_name="test1",
            title="Alert 1",
            description="Test",
        )
        ClinicalAlert.objects.create(
            patient=patient,
            alert_type="threshold",
            severity="orange",
            rule_name="test2",
            title="Alert 2",
            description="Test",
            status="resolved",
        )
        active = ClinicalDataService.get_patient_alerts(patient, status="active")
        assert len(active) == 1

        all_alerts = ClinicalDataService.get_patient_alerts(patient)
        assert len(all_alerts) == 2


class TestProcessPatientBatch:
    def test_batch_processing(self, patient, settings):
        settings.ENABLE_CLINICAL_DATA = True
        now = timezone.now()
        # Insert observations without processing
        for i in range(10):
            ClinicalDataService.ingest_observation(
                patient=patient,
                concept_id=CONCEPT_HEART_RATE,
                value_numeric=72,
                observed_at=now - timedelta(hours=i),
                skip_processing=True,
            )
        assert not PatientClinicalSnapshot.objects.filter(patient=patient).exists()

        # Process batch
        ClinicalDataService.process_patient_batch(patient)
        assert PatientClinicalSnapshot.objects.filter(patient=patient).exists()


class TestRiskScore:
    def test_risk_score_with_red_alert(self, patient):
        ClinicalAlert.objects.create(
            patient=patient,
            alert_type="threshold",
            severity="red",
            rule_name="test_risk",
            title="Test",
            description="Test",
        )
        score = ClinicalDataService._compute_risk_score(patient, TRAJECTORY_STABLE, 1)
        assert score >= Decimal("20")  # +20 for RED alert

    def test_risk_score_deteriorating_trajectory(self, patient):
        score = ClinicalDataService._compute_risk_score(patient, TRAJECTORY_DETERIORATING, 0)
        assert score >= Decimal("15")  # +15 for deteriorating

    def test_risk_score_capped_at_100(self, patient):
        # Create many alerts
        for i in range(10):
            ClinicalAlert.objects.create(
                patient=patient,
                alert_type="threshold",
                severity="red",
                rule_name=f"test_cap_{i}",
                title=f"Test {i}",
                description="Test",
            )
        score = ClinicalDataService._compute_risk_score(patient, TRAJECTORY_DETERIORATING, 10)
        assert score == Decimal("100")


class TestDataCompleteness:
    def test_completeness_zero_when_no_data(self, patient):
        comp = ClinicalDataService._compute_data_completeness(patient)
        assert comp == Decimal("0")

    def test_completeness_increases_with_data(self, patient):
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            skip_processing=True,
        )
        comp = ClinicalDataService._compute_data_completeness(patient)
        assert comp > Decimal("0")
