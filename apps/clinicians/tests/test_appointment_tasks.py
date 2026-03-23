"""Tests for appointment Celery tasks."""

import uuid
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.clinicians.models import Appointment, AppointmentRequest, Clinician
from apps.clinicians.tasks import (
    expire_appointment_requests,
    notify_upcoming_appointments,
    send_appointment_reminders,
)
from apps.patients.models import Hospital, Patient


@pytest.fixture
def hospital(db):
    return Hospital.objects.create(name="Task Hospital", code=f"TK-{uuid.uuid4().hex[:6]}")


@pytest.fixture
def clinician(hospital):
    clin_user = User.objects.create_user(
        username=f"dr_task_{uuid.uuid4().hex[:6]}",
        password="pass",  # pragma: allowlist secret
        role="clinician",
        first_name="Task",
        last_name="Doctor",
    )
    c = Clinician.objects.create(user=clin_user, role="physician", is_active=True)
    c.hospitals.add(hospital)
    return c


@pytest.fixture
def patient(hospital):
    pat_user = User.objects.create_user(
        username=f"pat_task_{uuid.uuid4().hex[:6]}",
        password="pass",  # pragma: allowlist secret
        role="patient",
        first_name="Task",
        last_name="Patient",
    )
    return Patient.objects.create(
        user=pat_user,
        hospital=hospital,
        date_of_birth=date(1975, 8, 22),
        leaflet_code=f"LC-{uuid.uuid4().hex[:6]}",
    )


@pytest.mark.django_db
class TestSendAppointmentReminders:
    def test_24h_reminder(self, patient, clinician):
        now = timezone.now()
        appt = Appointment.objects.create(
            clinician=clinician,
            patient=patient,
            scheduled_start=now + timedelta(hours=24),
            scheduled_end=now + timedelta(hours=24, minutes=30),
            appointment_type="follow_up",
            status="scheduled",
            reminder_24h_sent=False,
        )
        send_appointment_reminders()
        appt.refresh_from_db()
        assert appt.reminder_24h_sent is True

    def test_1h_reminder(self, patient, clinician):
        now = timezone.now()
        appt = Appointment.objects.create(
            clinician=clinician,
            patient=patient,
            scheduled_start=now + timedelta(hours=1),
            scheduled_end=now + timedelta(hours=1, minutes=30),
            appointment_type="follow_up",
            status="scheduled",
            reminder_1h_sent=False,
            virtual_visit_url="https://zoom.us/j/111",
        )
        send_appointment_reminders()
        appt.refresh_from_db()
        assert appt.reminder_1h_sent is True

    def test_reminder_not_sent_twice(self, patient, clinician):
        now = timezone.now()
        appt = Appointment.objects.create(
            clinician=clinician,
            patient=patient,
            scheduled_start=now + timedelta(hours=24),
            scheduled_end=now + timedelta(hours=24, minutes=30),
            appointment_type="follow_up",
            status="scheduled",
            reminder_24h_sent=True,  # Already sent
        )
        send_appointment_reminders()
        # Should not process already-sent reminders
        appt.refresh_from_db()
        assert appt.reminder_24h_sent is True


@pytest.mark.django_db
class TestExpireAppointmentRequests:
    def test_expires_old_pending(self, patient, clinician):
        now = timezone.now()
        req = AppointmentRequest.objects.create(
            patient=patient,
            clinician=clinician,
            trigger_type="clinician",
            reason="Old request",
            appointment_type="follow_up",
            earliest_notify_at=now - timedelta(days=20),
            expires_at=now - timedelta(days=1),
            status="pending",
        )
        result = expire_appointment_requests()
        req.refresh_from_db()
        assert req.status == "expired"
        assert result["expired"] >= 1

    def test_does_not_expire_future(self, patient, clinician):
        now = timezone.now()
        req = AppointmentRequest.objects.create(
            patient=patient,
            clinician=clinician,
            trigger_type="clinician",
            reason="Future request",
            appointment_type="follow_up",
            earliest_notify_at=now,
            expires_at=now + timedelta(days=7),
            status="pending",
        )
        expire_appointment_requests()
        req.refresh_from_db()
        assert req.status == "pending"


@pytest.mark.django_db
class TestNotifyUpcomingAppointments:
    def test_sends_notification(self, patient, clinician):
        now = timezone.now()
        AppointmentRequest.objects.create(
            patient=patient,
            clinician=clinician,
            trigger_type="milestone",
            reason="Day 7 check-in",
            appointment_type="check_in",
            earliest_notify_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=7),
            status="pending",
        )
        result = notify_upcoming_appointments()
        assert result["notified"] >= 1

    def test_booked_skipped(self, patient, clinician):
        now = timezone.now()
        AppointmentRequest.objects.create(
            patient=patient,
            clinician=clinician,
            trigger_type="milestone",
            reason="Already booked",
            appointment_type="check_in",
            earliest_notify_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=7),
            status="booked",
        )
        result = notify_upcoming_appointments()
        assert result["notified"] == 0
