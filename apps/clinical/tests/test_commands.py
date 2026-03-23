"""Tests for clinical management commands."""

import uuid

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.clinical.models import ClinicalObservation, PatientClinicalSnapshot


@pytest.fixture
def hospital(db):
    from apps.patients.models import Hospital

    return Hospital.objects.create(name="Test Hospital", code="CMD01")


@pytest.fixture
def patient(db, hospital):
    from apps.accounts.models import User
    from apps.patients.models import Patient

    user = User.objects.create_user(
        username=f"cmd_{uuid.uuid4().hex[:8]}",
        password="testpass123",
        first_name="Command",
        last_name="Test",
    )
    return Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1960-01-15",
        leaflet_code=uuid.uuid4().hex[:8],
        surgery_type="CABG",
    )


class TestSeedClinicalData:
    def test_refuses_in_production(self, settings):
        settings.DEBUG = False
        with pytest.raises(CommandError, match="DEBUG=True"):
            call_command("seed_clinical_data")

    def test_seeds_progressing_scenario(self, patient, settings):
        settings.DEBUG = True
        call_command("seed_clinical_data", patient_id=patient.pk, scenario="progressing", days=3)
        assert ClinicalObservation.objects.filter(patient=patient).count() > 0
        assert PatientClinicalSnapshot.objects.filter(patient=patient).exists()

    def test_seeds_chf_scenario(self, patient, settings):
        settings.DEBUG = True
        call_command("seed_clinical_data", patient_id=patient.pk, scenario="chf", days=3)
        assert ClinicalObservation.objects.filter(patient=patient).count() > 0

    def test_seeds_infection_scenario(self, patient, settings):
        settings.DEBUG = True
        call_command("seed_clinical_data", patient_id=patient.pk, scenario="infection", days=3)
        assert ClinicalObservation.objects.filter(patient=patient).count() > 0

    def test_seeds_declining_scenario(self, patient, settings):
        settings.DEBUG = True
        call_command("seed_clinical_data", patient_id=patient.pk, scenario="declining", days=3)
        assert ClinicalObservation.objects.filter(patient=patient).count() > 0

    def test_seeds_all_scenarios(self, patient, settings):
        settings.DEBUG = True
        call_command("seed_clinical_data", patient_id=patient.pk, scenario="all", days=3)
        assert ClinicalObservation.objects.filter(patient=patient).count() > 0

    def test_invalid_patient_id(self, db, settings):
        settings.DEBUG = True
        with pytest.raises(CommandError, match="not found"):
            call_command("seed_clinical_data", patient_id=99999)

    def test_no_patients(self, db, settings):
        settings.DEBUG = True
        from apps.patients.models import Patient

        Patient.objects.all().delete()
        with pytest.raises(CommandError, match="No patients found"):
            call_command("seed_clinical_data")


class TestComputeClinicalSnapshots:
    def test_recomputes_snapshots(self, patient, settings):
        settings.DEBUG = True
        # Seed some data first
        from apps.clinical.constants import CONCEPT_HEART_RATE
        from apps.clinical.services import ClinicalDataService

        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            skip_processing=True,
        )
        call_command("compute_clinical_snapshots")
        assert PatientClinicalSnapshot.objects.filter(patient=patient).exists()

    def test_skips_patients_without_observations(self, patient):
        call_command("compute_clinical_snapshots")
        assert not PatientClinicalSnapshot.objects.filter(patient=patient).exists()
