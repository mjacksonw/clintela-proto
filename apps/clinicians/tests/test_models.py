"""Tests for clinician models."""

import uuid as _uuid
from datetime import date, time

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.clinicians.models import (
    Appointment,
    Clinician,
    ClinicianAvailability,
    ClinicianNote,
)
from apps.patients.models import Hospital, Patient


class ClinicianModelTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test Hospital", code=f"TST-{_uuid.uuid4().hex[:8]}")
        self.user = User.objects.create_user(
            username="dr_test",
            password="pass",  # pragma: allowlist secret
            role="clinician",
            first_name="Test",
            last_name="Doctor",
        )
        self.clinician = Clinician.objects.create(
            user=self.user,
            role="physician",
            specialty="Ortho",
        )
        self.clinician.hospitals.add(self.hospital)

    def test_str(self):
        assert "Test Doctor" in str(self.clinician)
        assert "Physician" in str(self.clinician)

    def test_is_active_default(self):
        assert self.clinician.is_active is True


class ClinicianNoteTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test Hospital", code=f"TST-{_uuid.uuid4().hex[:8]}")
        self.clin_user = User.objects.create_user(
            username="dr_note",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        self.clinician = Clinician.objects.create(user=self.clin_user, role="nurse")
        self.pat_user = User.objects.create_user(
            username="patient_note",
            password="pass",  # pragma: allowlist secret
            role="patient",
            first_name="Pat",
            last_name="Ient",
        )
        self.patient = Patient.objects.create(
            user=self.pat_user,
            hospital=self.hospital,
            status="green",
            date_of_birth=date(1960, 1, 15),
            leaflet_code=f"LC-{_uuid.uuid4().hex[:8]}",
        )

    def test_create_note(self):
        note = ClinicianNote.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            content="Test note",
            note_type="quick_note",
        )
        assert note.id is not None
        assert note.is_pinned is False
        assert "quick_note" in str(note) or "Test" in str(note)

    def test_note_ordering(self):
        ClinicianNote.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            content="First",
        )
        ClinicianNote.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            content="Second",
        )
        notes = list(ClinicianNote.objects.filter(patient=self.patient))
        assert notes[0].content == "Second"  # newest first


class ClinicianAvailabilityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dr_avail",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        self.clinician = Clinician.objects.create(user=self.user, role="physician")

    def test_create_availability(self):
        avail = ClinicianAvailability.objects.create(
            clinician=self.clinician,
            day_of_week=0,
            start_time=time(7, 0),
            end_time=time(19, 0),
        )
        assert "Monday" in str(avail)

    def test_recurring_unique_constraint(self):
        ClinicianAvailability.objects.create(
            clinician=self.clinician,
            day_of_week=1,
            start_time=time(7, 0),
            end_time=time(19, 0),
            is_recurring=True,
        )
        with self.assertRaises(IntegrityError):
            ClinicianAvailability.objects.create(
                clinician=self.clinician,
                day_of_week=1,
                start_time=time(7, 0),
                end_time=time(15, 0),
                is_recurring=True,
            )

    def test_non_recurring_no_constraint(self):
        """Non-recurring availability should not hit uniqueness constraint."""
        from datetime import date

        ClinicianAvailability.objects.create(
            clinician=self.clinician,
            day_of_week=2,
            start_time=time(7, 0),
            end_time=time(12, 0),
            is_recurring=False,
            effective_date=date(2026, 3, 25),
        )
        ClinicianAvailability.objects.create(
            clinician=self.clinician,
            day_of_week=2,
            start_time=time(7, 0),
            end_time=time(15, 0),
            is_recurring=False,
            effective_date=date(2026, 4, 1),
        )
        assert (
            ClinicianAvailability.objects.filter(
                clinician=self.clinician,
                day_of_week=2,
            ).count()
            == 2
        )


class AppointmentTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test Hospital", code=f"TST-{_uuid.uuid4().hex[:8]}")
        self.clin_user = User.objects.create_user(
            username="dr_appt",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        self.clinician = Clinician.objects.create(user=self.clin_user, role="physician")
        self.pat_user = User.objects.create_user(
            username="patient_appt",
            password="pass",  # pragma: allowlist secret
            role="patient",
        )
        self.patient = Patient.objects.create(
            user=self.pat_user,
            hospital=self.hospital,
            status="green",
            date_of_birth=date(1960, 1, 15),
            leaflet_code=f"LC-{_uuid.uuid4().hex[:8]}",
        )

    def test_create_appointment(self):
        now = timezone.now()
        appt = Appointment.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            appointment_type="follow_up",
            scheduled_start=now,
            scheduled_end=now + timezone.timedelta(minutes=30),
        )
        assert appt.id is not None
        assert appt.status == "scheduled"
        assert isinstance(appt.id, _uuid.UUID)

    def test_appointment_ordering(self):
        now = timezone.now()
        Appointment.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            appointment_type="follow_up",
            scheduled_start=now + timezone.timedelta(hours=2),
            scheduled_end=now + timezone.timedelta(hours=2, minutes=30),
        )
        a2 = Appointment.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            appointment_type="check_in",
            scheduled_start=now + timezone.timedelta(hours=1),
            scheduled_end=now + timezone.timedelta(hours=1, minutes=30),
        )
        appts = list(Appointment.objects.filter(clinician=self.clinician))
        assert appts[0] == a2  # earlier first
