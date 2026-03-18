"""Test patients app."""

import pytest
from django.contrib.auth import get_user_model

from apps.patients.models import Hospital, Patient

User = get_user_model()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="patientuser",
        email="patient@example.com",
        password="testpass123",
    )


@pytest.fixture
def hospital():
    return Hospital.objects.create(
        name="Test Hospital",
        code="TEST001",
    )


@pytest.mark.django_db
def test_create_hospital(hospital):
    """Test creating a hospital."""
    assert hospital.name == "Test Hospital"
    assert hospital.code == "TEST001"
    assert hospital.is_active is True


@pytest.mark.django_db
def test_create_patient(user, hospital):
    """Test creating a patient."""
    from datetime import date

    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth=date(1980, 1, 1),
        leaflet_code="ABC123",
        surgery_type="Knee Replacement",
        surgery_date=date(2024, 1, 1),
    )

    assert patient.user == user
    assert patient.hospital == hospital
    assert patient.leaflet_code == "ABC123"
    assert patient.status == "green"
    assert patient.days_post_op() is not None


@pytest.mark.django_db
def test_hospital_str(hospital):
    """Test hospital string representation."""
    assert str(hospital) == "Test Hospital"


@pytest.mark.django_db
def test_patient_str(user, hospital):
    """Test patient string representation."""
    from datetime import date

    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth=date(1980, 1, 1),
        leaflet_code="ABC123",
    )
    assert "ABC123" in str(patient)


@pytest.mark.django_db
def test_patient_days_post_op(user, hospital):
    """Test days_post_op calculation."""
    from datetime import date, timedelta

    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth=date(1980, 1, 1),
        leaflet_code="ABC123",
        surgery_date=date.today() - timedelta(days=5),
    )
    assert patient.days_post_op() == 5


@pytest.mark.django_db
def test_patient_days_post_op_no_surgery(user, hospital):
    """Test days_post_op returns None when no surgery date."""
    from datetime import date

    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth=date(1980, 1, 1),
        leaflet_code="ABC123",
        surgery_date=None,
    )
    assert patient.days_post_op() is None
