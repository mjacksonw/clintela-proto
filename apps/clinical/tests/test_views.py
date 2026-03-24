"""Tests for clinical views (HTMX fragments)."""

import uuid
from decimal import Decimal

import pytest
from django.test import RequestFactory

from apps.clinical.constants import CONCEPT_HEART_RATE
from apps.clinical.models import PatientClinicalSnapshot
from apps.clinical.services import ClinicalDataService
from apps.clinical.views import health_card_fragment, vitals_tab_fragment


@pytest.fixture
def hospital(db):
    from apps.patients.models import Hospital

    return Hospital.objects.create(name="Test Hospital", code="VIEW01")


@pytest.fixture
def clinician_user(db, hospital):
    from apps.accounts.models import User
    from apps.clinicians.models import Clinician

    user = User.objects.create_user(
        username=f"clinician_{uuid.uuid4().hex[:8]}",
        password="testpass123",  # pragma: allowlist secret
        first_name="Dr.",
        last_name="View",
        role="clinician",
    )
    clinician = Clinician.objects.create(user=user, specialty="Cardiology")
    clinician.hospitals.add(hospital)
    return user


@pytest.fixture
def patient_user(db):
    from apps.accounts.models import User

    return User.objects.create_user(
        username=f"patient_{uuid.uuid4().hex[:8]}",
        password="testpass123",  # pragma: allowlist secret
        first_name="View",
        last_name="Patient",
        role="patient",
    )


@pytest.fixture
def patient(db, hospital, patient_user):
    from apps.patients.models import Patient

    return Patient.objects.create(
        user=patient_user,
        hospital=hospital,
        date_of_birth="1960-01-15",
        leaflet_code=uuid.uuid4().hex[:8],
        surgery_type="CABG",
    )


@pytest.fixture
def rf():
    return RequestFactory()


class TestVitalsTabFragment:
    def test_returns_empty_when_feature_off(self, rf, patient, clinician_user, settings):
        settings.ENABLE_CLINICAL_DATA = False
        request = rf.get(f"/clinical/clinician/patient/{patient.pk}/vitals/")
        request.user = clinician_user
        response = vitals_tab_fragment(request, patient.pk)
        assert response.status_code == 200
        assert response.content == b""

    def test_returns_empty_state_no_data(self, rf, patient, clinician_user, settings):
        settings.ENABLE_CLINICAL_DATA = True
        request = rf.get(f"/clinical/clinician/patient/{patient.pk}/vitals/")
        request.user = clinician_user
        response = vitals_tab_fragment(request, patient.pk)
        assert response.status_code == 200
        assert b"No clinical data available" in response.content

    def test_returns_chart_data_with_observations(self, rf, patient, clinician_user, settings):
        settings.ENABLE_CLINICAL_DATA = True
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            skip_processing=True,
        )
        ClinicalDataService.compute_snapshot(patient)

        request = rf.get(f"/clinical/clinician/patient/{patient.pk}/vitals/")
        request.user = clinician_user
        response = vitals_tab_fragment(request, patient.pk)
        assert response.status_code == 200
        assert b"chart-data" in response.content

    def test_unauthenticated_returns_403(self, rf, patient, settings):
        settings.ENABLE_CLINICAL_DATA = True
        from django.contrib.auth.models import AnonymousUser

        request = rf.get(f"/clinical/clinician/patient/{patient.pk}/vitals/")
        request.user = AnonymousUser()
        response = vitals_tab_fragment(request, patient.pk)
        assert response.status_code == 403


class TestHealthCardFragment:
    def test_returns_empty_when_feature_off(self, rf, patient, patient_user, settings):
        settings.ENABLE_CLINICAL_DATA = False
        request = rf.get("/clinical/patient/health-card/")
        request.user = patient_user
        response = health_card_fragment(request)
        assert response.status_code == 200
        assert response.content == b""

    def test_returns_empty_state_no_data(self, rf, patient, patient_user, settings):
        settings.ENABLE_CLINICAL_DATA = True
        request = rf.get("/clinical/patient/health-card/")
        request.user = patient_user
        response = health_card_fragment(request)
        assert response.status_code == 200
        assert b"Once we start tracking" in response.content

    def test_returns_sparklines_with_data(self, rf, patient, patient_user, settings):
        settings.ENABLE_CLINICAL_DATA = True
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            skip_processing=True,
        )
        ClinicalDataService.compute_snapshot(patient)

        request = rf.get("/clinical/patient/health-card/")
        request.user = patient_user
        response = health_card_fragment(request)
        assert response.status_code == 200
        assert b"My Health" in response.content

    def test_trajectory_message_improving(self, rf, patient, patient_user, settings):
        settings.ENABLE_CLINICAL_DATA = True
        # Need sparkline data to trigger the data branch (not empty state)
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            skip_processing=True,
        )
        PatientClinicalSnapshot.objects.create(
            patient=patient,
            trajectory="improving",
            risk_score=Decimal("10"),
            data_completeness=Decimal("0.8"),
        )
        request = rf.get("/clinical/patient/health-card/")
        request.user = patient_user
        response = health_card_fragment(request)
        assert b"looking great" in response.content

    def test_trajectory_message_concerning(self, rf, patient, patient_user, settings):
        settings.ENABLE_CLINICAL_DATA = True
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=CONCEPT_HEART_RATE,
            value_numeric=72,
            skip_processing=True,
        )
        PatientClinicalSnapshot.objects.create(
            patient=patient,
            trajectory="concerning",
            risk_score=Decimal("30"),
            data_completeness=Decimal("0.8"),
        )
        request = rf.get("/clinical/patient/health-card/")
        request.user = patient_user
        response = health_card_fragment(request)
        assert b"noticed some changes" in response.content
        assert b"not alone" in response.content

    def test_no_patient_profile_returns_empty(self, rf, clinician_user, settings):
        settings.ENABLE_CLINICAL_DATA = True
        request = rf.get("/clinical/patient/health-card/")
        request.user = clinician_user
        response = health_card_fragment(request)
        assert response.content == b""
