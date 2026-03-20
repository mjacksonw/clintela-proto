"""Tests for clinician services."""

import uuid
from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.agents.models import AgentConversation, AgentMessage, Escalation
from apps.clinicians.models import (
    Clinician,
    ClinicianAvailability,
    ClinicianNote,
)
from apps.clinicians.services import (
    HandoffService,
    PatientListService,
    SchedulingService,
    TakeControlService,
    TimelineService,
)
from apps.patients.models import Hospital, Patient


class ServiceTestBase(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            code=f"TST-{uuid.uuid4().hex[:8]}",
        )
        self.clin_user = User.objects.create_user(
            username="dr_svc",
            password="pass",  # pragma: allowlist secret
            role="clinician",
            first_name="Svc",
            last_name="Doctor",
        )
        self.clinician = Clinician.objects.create(
            user=self.clin_user,
            role="physician",
            is_active=True,
        )
        self.clinician.hospitals.add(self.hospital)

        self.pat_user = User.objects.create_user(
            username="pat_svc",
            password="pass",  # pragma: allowlist secret
            role="patient",
            first_name="Svc",
            last_name="Patient",
        )
        self.patient = Patient.objects.create(
            user=self.pat_user,
            hospital=self.hospital,
            status="yellow",
            lifecycle_status="post_op",
            surgery_type="Knee Replacement",
            date_of_birth=date(1960, 1, 15),
            leaflet_code=f"LC-{uuid.uuid4().hex[:8]}",
        )


class PatientListServiceTest(ServiceTestBase):
    def test_get_patients_severity_sort(self):
        # Create additional patients
        for status, name in [("red", "Red"), ("green", "Green")]:
            u = User.objects.create_user(
                username=f"pat_{name.lower()}",
                password="pass",  # pragma: allowlist secret
                role="patient",
                last_name=name,
            )
            Patient.objects.create(
                user=u,
                hospital=self.hospital,
                status=status,
                date_of_birth=date(1960, 1, 15),
                leaflet_code=f"LC-{uuid.uuid4().hex[:8]}",
            )

        patients = PatientListService.get_patients_for_clinician(self.clinician)
        assert len(patients) >= 3
        # Red should be first
        assert patients[0].status == "red"

    def test_get_patients_alpha_sort(self):
        patients = PatientListService.get_patients_for_clinician(
            self.clinician,
            sort="alpha",
        )
        assert len(patients) >= 1

    def test_get_patients_search(self):
        patients = PatientListService.get_patients_for_clinician(
            self.clinician,
            search="Svc",
        )
        assert len(patients) == 1

    def test_get_patients_search_no_match(self):
        patients = PatientListService.get_patients_for_clinician(
            self.clinician,
            search="NONEXISTENT",
        )
        assert len(patients) == 0

    def test_get_status_line_escalation(self):
        Escalation.objects.create(
            patient=self.patient,
            reason="Test escalation reason",
            severity="urgent",
            status="pending",
        )
        line = PatientListService.get_status_line(self.patient)
        assert "Test escalation" in line

    def test_get_status_line_last_message(self):
        conv = AgentConversation.objects.create(
            patient=self.patient,
            agent_type="supervisor",
        )
        AgentMessage.objects.create(
            conversation=conv,
            role="assistant",
            content="AI response text",
        )
        line = PatientListService.get_status_line(self.patient)
        assert "AI response" in line

    def test_get_status_line_lifecycle_fallback(self):
        line = PatientListService.get_status_line(self.patient)
        assert line  # Should return something


class HandoffServiceTest(ServiceTestBase):
    def test_handoff_with_escalations(self):
        Escalation.objects.create(
            patient=self.patient,
            reason="New esc",
            severity="urgent",
            status="pending",
        )
        summary = HandoffService.get_handoff_summary(
            self.clinician,
            timezone.now() - timedelta(hours=12),
        )
        assert summary["new_escalation_count"] >= 1

    def test_handoff_empty(self):
        summary = HandoffService.get_handoff_summary(
            self.clinician,
            timezone.now(),  # no changes since now
        )
        assert summary["new_escalation_count"] == 0


class TimelineServiceTest(ServiceTestBase):
    def test_timeline_empty(self):
        timeline = TimelineService.get_timeline(self.patient)
        assert isinstance(timeline, list)

    def test_timeline_with_events(self):
        Escalation.objects.create(
            patient=self.patient,
            reason="Timeline esc",
            severity="routine",
            status="pending",
        )
        ClinicianNote.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            content="Timeline note",
        )
        timeline = TimelineService.get_timeline(self.patient)
        assert len(timeline) >= 1
        # Today's date should have events
        today = timezone.now().date()
        today_group = next((g for g in timeline if g["date"] == today), None)
        assert today_group is not None
        assert today_group["counts"]["escalation"] >= 1
        assert today_group["counts"]["note"] >= 1


class TakeControlServiceTest(ServiceTestBase):
    def setUp(self):
        super().setUp()
        self.conversation = AgentConversation.objects.create(
            patient=self.patient,
            agent_type="supervisor",
            status="active",
        )

    def test_take_control_success(self):
        result = TakeControlService.take_control(
            self.conversation,
            self.clin_user,
        )
        assert result is True
        self.conversation.refresh_from_db()
        assert self.conversation.paused_by == self.clin_user
        assert self.conversation.paused_at is not None

    def test_take_control_race_condition(self):
        """Second clinician cannot take control when first has it."""
        TakeControlService.take_control(self.conversation, self.clin_user)

        other_user = User.objects.create_user(
            username="dr_race",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        result = TakeControlService.take_control(self.conversation, other_user)
        assert result is False

    def test_release_control(self):
        TakeControlService.take_control(self.conversation, self.clin_user)
        result = TakeControlService.release_control(
            self.conversation,
            self.clin_user,
        )
        assert result is True
        self.conversation.refresh_from_db()
        assert self.conversation.paused_by is None

    def test_release_control_wrong_user(self):
        TakeControlService.take_control(self.conversation, self.clin_user)
        other_user = User.objects.create_user(
            username="dr_wrong",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        result = TakeControlService.release_control(
            self.conversation,
            other_user,
        )
        assert result is False

    def test_release_stale_locks(self):
        TakeControlService.take_control(self.conversation, self.clin_user)
        # Manually backdate paused_at
        AgentConversation.objects.filter(pk=self.conversation.pk).update(
            paused_at=timezone.now() - timedelta(minutes=31),
        )
        released = TakeControlService.release_stale_locks(timeout_minutes=30)
        assert released == 1
        self.conversation.refresh_from_db()
        assert self.conversation.paused_by is None

    def test_release_stale_locks_not_expired(self):
        TakeControlService.take_control(self.conversation, self.clin_user)
        released = TakeControlService.release_stale_locks(timeout_minutes=30)
        assert released == 0


class SchedulingServiceTest(ServiceTestBase):
    def test_get_weekly_schedule_empty(self):
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        schedule = SchedulingService.get_weekly_schedule(self.clinician, monday)
        assert schedule["appointments"] == []

    def test_create_appointment_success(self):
        start = timezone.now() + timedelta(hours=2)
        end = start + timedelta(minutes=30)
        appt = SchedulingService.create_appointment(
            clinician=self.clinician,
            patient=self.patient,
            start=start,
            end=end,
            appointment_type="follow_up",
            created_by=self.clin_user,
        )
        assert appt is not None
        assert appt.status == "scheduled"

    def test_create_appointment_conflict(self):
        start = timezone.now() + timedelta(hours=2)
        end = start + timedelta(minutes=30)
        SchedulingService.create_appointment(
            clinician=self.clinician,
            patient=self.patient,
            start=start,
            end=end,
            appointment_type="follow_up",
        )
        # Overlapping appointment
        conflict = SchedulingService.create_appointment(
            clinician=self.clinician,
            patient=self.patient,
            start=start + timedelta(minutes=15),
            end=end + timedelta(minutes=15),
            appointment_type="check_in",
        )
        assert conflict is None

    def test_get_next_appointment(self):
        start = timezone.now() + timedelta(hours=2)
        SchedulingService.create_appointment(
            clinician=self.clinician,
            patient=self.patient,
            start=start,
            end=start + timedelta(minutes=30),
            appointment_type="follow_up",
        )
        nxt = SchedulingService.get_next_appointment(self.clinician)
        assert nxt is not None

    def test_get_patient_appointments(self):
        start = timezone.now() + timedelta(hours=2)
        SchedulingService.create_appointment(
            clinician=self.clinician,
            patient=self.patient,
            start=start,
            end=start + timedelta(minutes=30),
            appointment_type="follow_up",
        )
        appts = SchedulingService.get_patient_appointments(self.patient)
        assert appts.count() == 1

    def test_get_available_slots(self):
        ClinicianAvailability.objects.create(
            clinician=self.clinician,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(12, 0),
            is_recurring=True,
        )
        # Find a Monday
        today = date.today()
        monday = today + timedelta(days=(7 - today.weekday()) % 7)
        if today.weekday() == 0:
            monday = today

        slots = SchedulingService.get_available_slots(
            self.clinician,
            monday,
            duration_minutes=30,
        )
        assert len(slots) == 6  # 9:00-9:30, 9:30-10:00, ..., 11:30-12:00
