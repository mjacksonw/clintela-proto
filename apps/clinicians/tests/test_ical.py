"""Tests for iCal generation."""

import uuid
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.clinicians.ical import generate_ical_event
from apps.clinicians.models import Appointment, Clinician
from apps.patients.models import Hospital, Patient


@pytest.fixture
def appointment(db):
    hospital = Hospital.objects.create(name="iCal Hospital", code=f"ICL-{uuid.uuid4().hex[:6]}")
    clin_user = User.objects.create_user(
        username=f"dr_ical_{uuid.uuid4().hex[:6]}",
        password="pass",  # pragma: allowlist secret
        role="clinician",
        first_name="Sarah",
        last_name="Smith",
    )
    clinician = Clinician.objects.create(user=clin_user, role="physician", is_active=True)
    clinician.hospitals.add(hospital)
    pat_user = User.objects.create_user(
        username=f"pat_ical_{uuid.uuid4().hex[:6]}",
        password="pass",  # pragma: allowlist secret
        role="patient",
        first_name="Bob",
        last_name="Jones",
    )
    patient = Patient.objects.create(
        user=pat_user,
        hospital=hospital,
        date_of_birth=date(1980, 3, 15),
        leaflet_code=f"LC-{uuid.uuid4().hex[:6]}",
    )
    now = timezone.now()
    return Appointment.objects.create(
        clinician=clinician,
        patient=patient,
        scheduled_start=now + timedelta(days=1),
        scheduled_end=now + timedelta(days=1, minutes=30),
        appointment_type="follow_up",
        virtual_visit_url="https://zoom.us/j/999",
        notes="Post-op follow up",
    )


@pytest.mark.django_db
class TestGenerateIcalEvent:
    def test_generates_valid_ics_bytes(self, appointment):
        result = generate_ical_event(appointment)
        assert isinstance(result, bytes)
        assert b"BEGIN:VCALENDAR" in result
        assert b"END:VCALENDAR" in result
        assert b"BEGIN:VEVENT" in result

    def test_contains_summary(self, appointment):
        result = generate_ical_event(appointment)
        assert b"SUMMARY" in result
        assert b"Sarah Smith" in result
        assert b"Follow Up" in result

    def test_contains_zoom_link(self, appointment):
        result = generate_ical_event(appointment)
        assert b"zoom.us/j/999" in result
        assert b"LOCATION" in result

    def test_datetime_format(self, appointment):
        result = generate_ical_event(appointment)
        # iCal uses DTSTART and DTEND
        assert b"DTSTART" in result
        assert b"DTEND" in result
