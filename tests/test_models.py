"""Test all app models for coverage."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model

from apps.caregivers.models import Caregiver, CaregiverRelationship
from apps.clinicians.models import Clinician
from apps.pathways.models import ClinicalPathway
from apps.patients.models import Hospital, Patient

User = get_user_model()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
def hospital():
    return Hospital.objects.create(
        name="Test Hospital",
        code="TEST001",
    )


@pytest.mark.django_db
def test_clinician_str(user, hospital):
    """Test clinician string representation."""
    clinician = Clinician.objects.create(
        user=user,
        role="physician",
    )
    clinician.hospitals.add(hospital)
    assert "Physician" in str(clinician)


@pytest.mark.django_db
def test_caregiver_str(user):
    """Test caregiver string representation."""
    caregiver = Caregiver.objects.create(
        user=user,
    )
    assert "Caregiver" in str(caregiver)


@pytest.mark.django_db
def test_caregiver_relationship(user, hospital):
    """Test caregiver relationship."""
    patient_user = User.objects.create_user(
        username="patientuser",
        email="patient@example.com",
        password="testpass123",
    )
    patient = Patient.objects.create(
        user=patient_user,
        hospital=hospital,
        date_of_birth=date(1980, 1, 1),
        leaflet_code="PAT001",
    )
    caregiver = Caregiver.objects.create(user=user)
    relationship = CaregiverRelationship.objects.create(
        caregiver=caregiver,
        patient=patient,
        relationship="Spouse",
    )
    assert str(relationship) == "Spouse"


@pytest.mark.django_db
def test_clinical_pathway_str():
    """Test clinical pathway string representation."""
    pathway = ClinicalPathway.objects.create(
        name="Knee Replacement Recovery",
        surgery_type="Knee Replacement",
        description="Standard recovery protocol",
        duration_days=90,
    )
    assert str(pathway) == "Knee Replacement Recovery"
