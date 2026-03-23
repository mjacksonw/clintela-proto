"""Tests for clinical Celery tasks."""

import uuid

import pytest
from django.utils import timezone

from apps.clinical.constants import CONCEPT_BODY_WEIGHT, CONCEPT_HEART_RATE
from apps.clinical.models import ClinicalAlert, PatientClinicalSnapshot
from apps.clinical.services import ClinicalDataService
from apps.clinical.tasks import check_missing_data, compute_all_snapshots


@pytest.fixture
def hospital(db):
    from apps.patients.models import Hospital

    return Hospital.objects.create(name="Test Hospital", code="TASK01")


@pytest.fixture
def patient(db, hospital):
    from apps.accounts.models import User
    from apps.patients.models import Patient

    user = User.objects.create_user(
        username=f"task_{uuid.uuid4().hex[:8]}",
        password="testpass123",
        first_name="Task",
        last_name="Test",
    )
    return Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1960-01-15",
        leaflet_code=uuid.uuid4().hex[:8],
        surgery_type="CABG",
    )


class TestComputeAllSnapshots:
    def test_recomputes_snapshots(self, patient):
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            skip_processing=True,
        )
        result = compute_all_snapshots()
        assert result == 1
        assert PatientClinicalSnapshot.objects.filter(patient=patient).exists()

    def test_skips_patients_without_observations(self, patient):
        result = compute_all_snapshots()
        assert result == 0

    def test_handles_multiple_patients(self, hospital):
        from apps.accounts.models import User
        from apps.patients.models import Patient

        patients = []
        for _i in range(3):
            user = User.objects.create_user(
                username=f"multi_{uuid.uuid4().hex[:8]}",
                password="testpass123",
            )
            p = Patient.objects.create(
                user=user,
                hospital=hospital,
                date_of_birth="1960-01-15",
                leaflet_code=uuid.uuid4().hex[:8],
            )
            ClinicalDataService.ingest_observation(
                patient=p,
                concept_id=CONCEPT_HEART_RATE,
                value_numeric=72,
                skip_processing=True,
            )
            patients.append(p)

        result = compute_all_snapshots()
        assert result == 3


class TestCheckMissingData:
    def test_no_alerts_when_data_recent(self, patient):
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            skip_processing=True,
        )
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_BODY_WEIGHT,
            value_numeric=185,
            skip_processing=True,
        )
        result = check_missing_data()
        assert result == 0

    def test_creates_alert_for_stale_data(self, patient):
        from datetime import timedelta

        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_BODY_WEIGHT,
            value_numeric=185,
            observed_at=timezone.now() - timedelta(hours=50),
            skip_processing=True,
        )
        result = check_missing_data()
        assert result >= 1
        assert ClinicalAlert.objects.filter(patient=patient, rule_name="missing_weight").exists()

    def test_no_patients_returns_zero(self, db):
        result = check_missing_data()
        assert result == 0
