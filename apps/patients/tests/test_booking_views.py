"""Tests for patient booking views."""

import uuid
from datetime import date, time, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.clinicians.models import (
    Appointment,
    AppointmentRequest,
    Clinician,
    ClinicianAvailability,
)
from apps.patients.models import Hospital, Patient


@pytest.fixture
def hospital(db):
    return Hospital.objects.create(name="Booking Hospital", code=f"BK-{uuid.uuid4().hex[:6]}")


@pytest.fixture
def clinician(hospital):
    clin_user = User.objects.create_user(
        username=f"dr_bk_{uuid.uuid4().hex[:6]}",
        password="pass",  # pragma: allowlist secret
        role="clinician",
        first_name="Alice",
        last_name="Booker",
    )
    c = Clinician.objects.create(
        user=clin_user,
        role="physician",
        is_active=True,
        zoom_link="https://zoom.us/j/booking",
    )
    c.hospitals.add(hospital)
    # Add availability Mon-Fri 9-17
    for dow in range(5):
        ClinicianAvailability.objects.create(
            clinician=c,
            day_of_week=dow,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_recurring=True,
        )
    return c


@pytest.fixture
def patient(hospital):
    pat_user = User.objects.create_user(
        username=f"pat_bk_{uuid.uuid4().hex[:6]}",
        password="pass",  # pragma: allowlist secret
        role="patient",
        first_name="Pat",
        last_name="Booker",
    )
    return Patient.objects.create(
        user=pat_user,
        hospital=hospital,
        date_of_birth=date(1985, 6, 20),
        leaflet_code=f"LC-{uuid.uuid4().hex[:6]}",
    )


@pytest.fixture
def authenticated_client(patient):
    client = Client()
    session = client.session
    session["patient_id"] = str(patient.id)
    session["authenticated"] = True
    session.save()
    return client


@pytest.fixture
def pending_request(patient, clinician):
    now = timezone.now()
    return AppointmentRequest.objects.create(
        patient=patient,
        clinician=clinician,
        trigger_type="clinician",
        reason="Follow-up needed",
        appointment_type="follow_up",
        earliest_notify_at=now,
        expires_at=now + timedelta(days=14),
    )


@pytest.fixture
def booked_appointment(patient, clinician):
    now = timezone.now()
    return Appointment.objects.create(
        clinician=clinician,
        patient=patient,
        scheduled_start=now + timedelta(days=2),
        scheduled_end=now + timedelta(days=2, minutes=30),
        appointment_type="follow_up",
        virtual_visit_url="https://zoom.us/j/booking",
    )


@pytest.mark.django_db
class TestBookingPageView:
    def test_renders_for_authenticated_patient(self, authenticated_client, pending_request):
        url = reverse("patients:booking_page", kwargs={"request_id": pending_request.id})
        response = authenticated_client.get(url)
        assert response.status_code == 200

    def test_unauthenticated_redirects(self, pending_request):
        client = Client()
        url = reverse("patients:booking_page", kwargs={"request_id": pending_request.id})
        response = client.get(url)
        assert response.status_code == 302

    def test_expired_request_redirects(self, authenticated_client, patient, clinician):
        now = timezone.now()
        expired = AppointmentRequest.objects.create(
            patient=patient,
            clinician=clinician,
            trigger_type="clinician",
            reason="Expired",
            appointment_type="follow_up",
            status="expired",
            earliest_notify_at=now - timedelta(days=20),
            expires_at=now - timedelta(days=1),
        )
        url = reverse("patients:booking_page", kwargs={"request_id": expired.id})
        response = authenticated_client.get(url)
        # Expired request has status != "pending" so it redirects to dashboard
        assert response.status_code == 302


@pytest.mark.django_db
class TestBookSlotView:
    def test_creates_appointment(self, authenticated_client, pending_request, patient):
        now = timezone.now()
        start = now + timedelta(days=3)
        end = start + timedelta(minutes=30)
        url = reverse("patients:book_slot", kwargs={"request_id": pending_request.id})
        response = authenticated_client.post(
            url,
            {
                "slot_start": start.isoformat(),
                "slot_end": end.isoformat(),
            },
        )
        # Should redirect to confirmation
        assert response.status_code == 302
        assert "booking-confirmed" in response.url
        pending_request.refresh_from_db()
        assert pending_request.status == "booked"

    def test_unauthenticated_returns_403(self, pending_request):
        client = Client()
        url = reverse("patients:book_slot", kwargs={"request_id": pending_request.id})
        response = client.post(url, {"slot_start": "x", "slot_end": "y"})
        assert response.status_code == 403

    def test_missing_slot_redirects(self, authenticated_client, pending_request):
        url = reverse("patients:book_slot", kwargs={"request_id": pending_request.id})
        response = authenticated_client.post(url, {})
        assert response.status_code == 302

    def test_invalid_datetime_redirects(self, authenticated_client, pending_request):
        url = reverse("patients:book_slot", kwargs={"request_id": pending_request.id})
        response = authenticated_client.post(url, {"slot_start": "not-a-date", "slot_end": "also-bad"})
        assert response.status_code == 302

    def test_conflict_shows_error(self, authenticated_client, pending_request, patient, clinician):
        now = timezone.now()
        start = now + timedelta(days=3)
        end = start + timedelta(minutes=30)
        # Pre-book the slot
        Appointment.objects.create(
            clinician=clinician,
            patient=patient,
            scheduled_start=start,
            scheduled_end=end,
            appointment_type="follow_up",
        )
        url = reverse("patients:book_slot", kwargs={"request_id": pending_request.id})
        response = authenticated_client.post(
            url,
            {
                "slot_start": start.isoformat(),
                "slot_end": end.isoformat(),
            },
        )
        assert response.status_code == 302


@pytest.mark.django_db
class TestBookingConfirmationView:
    def test_shows_confirmation(self, authenticated_client, booked_appointment):
        url = reverse(
            "patients:booking_confirmation",
            kwargs={"appointment_id": booked_appointment.id},
        )
        response = authenticated_client.get(url)
        assert response.status_code == 200

    def test_unauthenticated_redirects(self, booked_appointment):
        client = Client()
        url = reverse(
            "patients:booking_confirmation",
            kwargs={"appointment_id": booked_appointment.id},
        )
        response = client.get(url)
        assert response.status_code == 302

    def test_nonexistent_appointment_redirects(self, authenticated_client):
        fake_id = uuid.uuid4()
        url = reverse(
            "patients:booking_confirmation",
            kwargs={"appointment_id": fake_id},
        )
        response = authenticated_client.get(url)
        assert response.status_code == 302


@pytest.mark.django_db
class TestDownloadIcalView:
    def test_returns_ics_file(self, authenticated_client, booked_appointment):
        url = reverse(
            "patients:download_ical",
            kwargs={"appointment_id": booked_appointment.id},
        )
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "text/calendar; charset=utf-8"
        assert b"BEGIN:VCALENDAR" in response.content

    def test_unauthenticated_returns_403(self, booked_appointment):
        client = Client()
        url = reverse(
            "patients:download_ical",
            kwargs={"appointment_id": booked_appointment.id},
        )
        response = client.get(url)
        assert response.status_code == 403

    def test_nonexistent_returns_404(self, authenticated_client):
        fake_id = uuid.uuid4()
        url = reverse(
            "patients:download_ical",
            kwargs={"appointment_id": fake_id},
        )
        response = authenticated_client.get(url)
        assert response.status_code == 404
