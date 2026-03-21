"""Additional coverage tests for clinician views — targets uncovered lines."""

import uuid as _uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.agents.models import AgentConversation, AgentMessage, Escalation
from apps.clinicians.models import Appointment, Clinician, ClinicianAvailability
from apps.patients.models import Hospital, Patient

_DOB = "1960-01-15"


def _code():
    return f"TST-{_uuid.uuid4().hex[:8]}"


def _lc():
    return f"LC-{_uuid.uuid4().hex[:8]}"


class CoverageTestBase(TestCase):
    """Base class with common setup matching existing test patterns."""

    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test Hospital", code=_code())
        self.clin_user = User.objects.create_user(
            username=f"dr_cov_{_uuid.uuid4().hex[:6]}",
            password="testpass",  # pragma: allowlist secret
            role="clinician",
            first_name="Coverage",
            last_name="Doctor",
        )
        self.clinician = Clinician.objects.create(
            user=self.clin_user,
            role="physician",
            is_active=True,
        )
        self.clinician.hospitals.add(self.hospital)

        self.pat_user = User.objects.create_user(
            username=f"pat_cov_{_uuid.uuid4().hex[:6]}",
            password="testpass",  # pragma: allowlist secret
            role="patient",
            first_name="Coverage",
            last_name="Patient",
        )
        self.patient = Patient.objects.create(
            user=self.pat_user,
            hospital=self.hospital,
            status="yellow",
            lifecycle_status="post_op",
            surgery_type="Knee Replacement",
            date_of_birth=_DOB,
            leaflet_code=_lc(),
        )
        self.client.login(username=self.clin_user.username, password="testpass")  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Care Plan tab — active pathway branch (lines 194-208)
# ---------------------------------------------------------------------------


class CarePlanWithPathwayTest(CoverageTestBase):
    def test_care_plan_with_active_pathway(self):
        """Cover the milestones annotation branch when active pathway exists."""
        from apps.pathways.models import ClinicalPathway, PathwayMilestone, PatientPathway

        pathway = ClinicalPathway.objects.create(
            name="Knee Recovery",
            surgery_type="Knee Replacement",
            description="Recovery pathway",
            duration_days=90,
            is_active=True,
        )
        PatientPathway.objects.create(
            patient=self.patient,
            pathway=pathway,
            status="active",
        )
        PathwayMilestone.objects.create(
            pathway=pathway,
            title="Day 1 Check",
            description="First milestone",
            day=1,
            phase="early",
        )

        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/care-plan/",
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Research chat send (lines 253-278)
# ---------------------------------------------------------------------------


class ResearchChatSendTest(CoverageTestBase):
    def test_research_send_empty_message_rejected(self):
        """Line 259: empty message → 400."""
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/research/send/",
            {"message": ""},
        )
        assert response.status_code == 400

    @patch("apps.clinicians.services.ClinicianResearchService.send_research_message")
    def test_research_send_success(self, mock_send):
        """Lines 261-278: successful research message."""
        # Build a fake agent message return value
        fake_conv = AgentConversation.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            agent_type="clinician_research",
            status="active",
        )
        fake_msg = AgentMessage.objects.create(
            conversation=fake_conv,
            role="assistant",
            agent_type="clinician_research",
            content="Research answer here.",
        )
        mock_send.return_value = {
            "message": fake_msg,
            "response": "Research answer here.",
            "agent_type": "clinician_research",
            "metadata": {},
        }

        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/research/send/",
            {"message": "What are the risks?"},
        )
        assert response.status_code == 200
        assert mock_send.called

    @patch("apps.clinicians.services.ClinicianResearchService.send_research_message")
    def test_research_send_with_specialist_override(self, mock_send):
        """Lines 256, 264: specialist_override is forwarded."""
        fake_conv = AgentConversation.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            agent_type="clinician_research",
            status="active",
        )
        fake_msg = AgentMessage.objects.create(
            conversation=fake_conv,
            role="assistant",
            agent_type="clinician_research",
            content="Specialist answer.",
        )
        mock_send.return_value = {
            "message": fake_msg,
            "response": "Specialist answer.",
            "agent_type": "orthopedic",
            "metadata": {},
        }

        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/research/send/",
            {"message": "Specialist question", "specialist_override": "orthopedic"},
        )
        assert response.status_code == 200
        _, kwargs = mock_send.call_args
        assert kwargs.get("specialist_override") == "orthopedic" or mock_send.call_args[0][3] == "orthopedic"


# ---------------------------------------------------------------------------
# Inject message edge cases (lines 400, 407-417, 428-430, 451-452)
# ---------------------------------------------------------------------------


class InjectMessageEdgeCasesTest(CoverageTestBase):
    def test_inject_take_control_fails(self):
        """Line 400: TakeControlService.take_control returns False → error HTML."""
        AgentConversation.objects.create(
            patient=self.patient,
            agent_type="supervisor",
            status="active",
        )

        with patch("apps.clinicians.services.TakeControlService.take_control", return_value=False):
            response = self.client.post(
                f"/clinician/patients/{self.patient.id}/inject-message/",
                {"message": "Hello"},
            )
        assert response.status_code == 200
        # Should render the take control error template
        assert b"taken control" in response.content or b"Another clinician" in response.content

    def test_inject_other_clinician_has_control(self):
        """Lines 407-414: conversation.paused_by != request.user → error with name."""
        other_user = User.objects.create_user(
            username=f"dr_other_{_uuid.uuid4().hex[:6]}",
            password="testpass",  # pragma: allowlist secret
            role="clinician",
            first_name="Other",
            last_name="Doctor",
        )
        AgentConversation.objects.create(
            patient=self.patient,
            agent_type="supervisor",
            status="active",
            paused_by=other_user,
        )

        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/inject-message/",
            {"message": "Take over"},
        )
        assert response.status_code == 200
        assert b"currently responding" in response.content

    def test_inject_message_create_exception(self):
        """Lines 428-430: AgentMessage.objects.create raises → 400."""
        conv = AgentConversation.objects.create(
            patient=self.patient,
            agent_type="supervisor",
            status="active",
        )
        # Take control first so we own the conversation
        conv.paused_by = self.clin_user
        conv.save()

        with patch("apps.agents.models.AgentMessage.objects.create", side_effect=Exception("DB error")):
            response = self.client.post(
                f"/clinician/patients/{self.patient.id}/inject-message/",
                {"message": "Will fail"},
            )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Release control — no conversation found (lines 481-485)
# ---------------------------------------------------------------------------


class ReleaseControlNoneTest(CoverageTestBase):
    def test_release_control_no_conversation(self):
        """Lines 481-485: no conversation paused_by this user → still returns 200."""
        # No conversation at all — just release
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/take-control/release/",
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Add note — invalid note type (line 505)
# ---------------------------------------------------------------------------


class AddNoteInvalidTypeTest(CoverageTestBase):
    def test_add_note_invalid_type(self):
        """Line 505: invalid note_type → 400."""
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/notes/add/",
            {"content": "Some note", "note_type": "invalid_type"},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Acknowledge escalation — not found (lines 533-534)
# ---------------------------------------------------------------------------


class AcknowledgeEscalationNotFoundTest(CoverageTestBase):
    def test_acknowledge_not_found(self):
        """Lines 533-534: escalation DoesNotExist → 400."""
        fake_id = _uuid.uuid4()
        response = self.client.post(
            f"/clinician/escalations/{fake_id}/acknowledge/",
        )
        assert response.status_code == 400

    def test_acknowledge_idor_wrong_hospital(self):
        """Lines 537-539: escalation from different hospital → 403."""
        other_hospital = Hospital.objects.create(name="Other Hosp", code=_code())
        other_user = User.objects.create_user(
            username=f"idor_pat_{_uuid.uuid4().hex[:6]}",
            password="pass",  # pragma: allowlist secret
            role="patient",
        )
        other_patient = Patient.objects.create(
            user=other_user,
            hospital=other_hospital,
            status="green",
            date_of_birth=_DOB,
            leaflet_code=_lc(),
        )
        esc = Escalation.objects.create(
            patient=other_patient,
            reason="Test",
            severity="routine",
            status="pending",
        )
        response = self.client.post(
            f"/clinician/escalations/{esc.id}/acknowledge/",
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Resolve escalation — not found + IDOR (lines 557-558, 562)
# ---------------------------------------------------------------------------


class ResolveEscalationTest(CoverageTestBase):
    def test_resolve_not_found(self):
        """Lines 557-558: escalation DoesNotExist → 400."""
        fake_id = _uuid.uuid4()
        response = self.client.post(
            f"/clinician/escalations/{fake_id}/resolve/",
        )
        assert response.status_code == 400

    def test_resolve_idor_wrong_hospital(self):
        """Line 562: escalation from different hospital → 403."""
        other_hospital = Hospital.objects.create(name="Other Hosp2", code=_code())
        other_user = User.objects.create_user(
            username=f"idor_pat2_{_uuid.uuid4().hex[:6]}",
            password="pass",  # pragma: allowlist secret
            role="patient",
        )
        other_patient = Patient.objects.create(
            user=other_user,
            hospital=other_hospital,
            status="green",
            date_of_birth=_DOB,
            leaflet_code=_lc(),
        )
        esc = Escalation.objects.create(
            patient=other_patient,
            reason="Test",
            severity="routine",
            status="pending",
        )
        response = self.client.post(
            f"/clinician/escalations/{esc.id}/resolve/",
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Bulk acknowledge — edge cases (lines 580, 593-595)
# ---------------------------------------------------------------------------


class BulkAcknowledgeEdgeCasesTest(CoverageTestBase):
    def test_bulk_acknowledge_no_ids(self):
        """Line 580: no escalation_ids → 400."""
        response = self.client.post(
            "/clinician/escalations/bulk-acknowledge/",
            {},
        )
        assert response.status_code == 400

    def test_bulk_acknowledge_wrong_hospital(self):
        """Lines 593-595: escalation from different hospital is counted as failed."""
        other_hospital = Hospital.objects.create(name="Bulk Other Hosp", code=_code())
        other_user = User.objects.create_user(
            username=f"bulk_pat_{_uuid.uuid4().hex[:6]}",
            password="pass",  # pragma: allowlist secret
            role="patient",
        )
        other_patient = Patient.objects.create(
            user=other_user,
            hospital=other_hospital,
            status="green",
            date_of_birth=_DOB,
            leaflet_code=_lc(),
        )
        esc = Escalation.objects.create(
            patient=other_patient,
            reason="Cross-hospital",
            severity="routine",
            status="pending",
        )
        response = self.client.post(
            "/clinician/escalations/bulk-acknowledge/",
            {"escalation_ids": [str(esc.id)]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["failed"] == 1
        assert data["acknowledged"] == 0

    def test_bulk_acknowledge_nonexistent_id(self):
        """Lines 594-595: DoesNotExist branch increments failed."""
        fake_id = str(_uuid.uuid4())
        response = self.client.post(
            "/clinician/escalations/bulk-acknowledge/",
            {"escalation_ids": [fake_id]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["failed"] == 1


# ---------------------------------------------------------------------------
# Lifecycle — missing new_status (line 620)
# ---------------------------------------------------------------------------


class LifecycleMissingStatusTest(CoverageTestBase):
    def test_lifecycle_no_status(self):
        """Line 620: missing new_status → 400."""
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/lifecycle/",
            {},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Save availability (lines 698-719)
# ---------------------------------------------------------------------------


class SaveAvailabilityTest(CoverageTestBase):
    def test_save_availability_success(self):
        """Lines 711-719: valid availability → saved + redirect."""
        response = self.client.post(
            "/clinician/schedule/availability/",
            {
                "day_of_week": "1",
                "start_time": "09:00",
                "end_time": "17:00",
            },
        )
        # Redirects to schedule
        assert response.status_code == 302
        assert ClinicianAvailability.objects.filter(clinician=self.clinician).exists()

    def test_save_availability_invalid_day(self):
        """Lines 703-704: invalid day_of_week → 400."""
        response = self.client.post(
            "/clinician/schedule/availability/",
            {
                "day_of_week": "not_a_number",
                "start_time": "09:00",
                "end_time": "17:00",
            },
        )
        assert response.status_code == 400

    def test_save_availability_missing_times(self):
        """Lines 708-709: missing start/end time → 400."""
        response = self.client.post(
            "/clinician/schedule/availability/",
            {
                "day_of_week": "1",
                "start_time": "",
                "end_time": "",
            },
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Create appointment (lines 726-775)
# ---------------------------------------------------------------------------


class CreateAppointmentTest(CoverageTestBase):
    def _start_end(self, days_ahead=1):
        start = timezone.now() + timedelta(days=days_ahead)
        end = start + timedelta(hours=1)
        return start.isoformat(), end.isoformat()

    def test_create_appointment_success(self):
        """Lines 762-775: valid appointment → created + redirect."""
        start_str, end_str = self._start_end()
        response = self.client.post(
            "/clinician/schedule/appointments/create/",
            {
                "patient_id": str(self.patient.id),
                "appointment_type": "follow_up",
                "scheduled_start": start_str,
                "scheduled_end": end_str,
                "notes": "Test appointment",
            },
        )
        assert response.status_code == 302
        assert Appointment.objects.filter(clinician=self.clinician, patient=self.patient).exists()

    def test_create_appointment_missing_fields(self):
        """Lines 737-738: missing required fields → 400."""
        response = self.client.post(
            "/clinician/schedule/appointments/create/",
            {"appointment_type": "follow_up"},
        )
        assert response.status_code == 400

    def test_create_appointment_invalid_type(self):
        """Lines 741-742: invalid appointment_type → 400."""
        start_str, end_str = self._start_end()
        response = self.client.post(
            "/clinician/schedule/appointments/create/",
            {
                "patient_id": str(self.patient.id),
                "appointment_type": "invalid_type",
                "scheduled_start": start_str,
                "scheduled_end": end_str,
            },
        )
        assert response.status_code == 400

    def test_create_appointment_patient_not_found(self):
        """Lines 748-749: patient DoesNotExist → 400."""
        start_str, end_str = self._start_end()
        response = self.client.post(
            "/clinician/schedule/appointments/create/",
            {
                "patient_id": "99999",
                "appointment_type": "follow_up",
                "scheduled_start": start_str,
                "scheduled_end": end_str,
            },
        )
        assert response.status_code == 400

    def test_create_appointment_idor(self):
        """Lines 753-754: patient from different hospital → 403."""
        other_hospital = Hospital.objects.create(name="Other Sched Hosp", code=_code())
        other_user = User.objects.create_user(
            username=f"sched_pat_{_uuid.uuid4().hex[:6]}",
            password="pass",  # pragma: allowlist secret
            role="patient",
        )
        other_patient = Patient.objects.create(
            user=other_user,
            hospital=other_hospital,
            status="green",
            date_of_birth=_DOB,
            leaflet_code=_lc(),
        )
        start_str, end_str = self._start_end()
        response = self.client.post(
            "/clinician/schedule/appointments/create/",
            {
                "patient_id": str(other_patient.id),
                "appointment_type": "follow_up",
                "scheduled_start": start_str,
                "scheduled_end": end_str,
            },
        )
        assert response.status_code == 403

    def test_create_appointment_invalid_date_format(self):
        """Lines 759-760: invalid ISO date → 400."""
        response = self.client.post(
            "/clinician/schedule/appointments/create/",
            {
                "patient_id": str(self.patient.id),
                "appointment_type": "follow_up",
                "scheduled_start": "not-a-date",
                "scheduled_end": "also-not-a-date",
            },
        )
        assert response.status_code == 400

    def test_create_appointment_conflict(self):
        """Lines 772-773: conflicting appointment → 400."""
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=1)
        # Create an existing appointment in same slot
        Appointment.objects.create(
            clinician=self.clinician,
            patient=self.patient,
            scheduled_start=start,
            scheduled_end=end,
            appointment_type="follow_up",
            status="scheduled",
        )

        response = self.client.post(
            "/clinician/schedule/appointments/create/",
            {
                "patient_id": str(self.patient.id),
                "appointment_type": "check_in",
                "scheduled_start": start.isoformat(),
                "scheduled_end": end.isoformat(),
            },
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Cancel appointment (lines 782-795)
# ---------------------------------------------------------------------------


class CancelAppointmentTest(CoverageTestBase):
    def test_cancel_appointment_success(self):
        """Lines 792-795: valid cancel → status=cancelled + redirect."""
        start = timezone.now() + timedelta(days=3)
        end = start + timedelta(hours=1)
        appt = Appointment.objects.create(
            clinician=self.clinician,
            patient=self.patient,
            scheduled_start=start,
            scheduled_end=end,
            appointment_type="follow_up",
            status="scheduled",
        )
        response = self.client.post(
            f"/clinician/schedule/appointments/{appt.id}/cancel/",
        )
        assert response.status_code == 302
        appt.refresh_from_db()
        assert appt.status == "cancelled"

    def test_cancel_appointment_not_found(self):
        """Lines 789-790: appointment DoesNotExist → 400."""
        fake_id = _uuid.uuid4()
        response = self.client.post(
            f"/clinician/schedule/appointments/{fake_id}/cancel/",
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Timeline day — day found in grouped data (lines 868-870)
# ---------------------------------------------------------------------------


class TimelineDayFoundTest(CoverageTestBase):
    def test_timeline_day_with_matching_event(self):
        """Lines 868-870: date matches a group in timeline → day_events populated."""
        # Create an escalation so the timeline has an event for today
        Escalation.objects.create(
            patient=self.patient,
            reason="Timeline test escalation",
            severity="routine",
            status="pending",
        )
        today = timezone.now().date().isoformat()
        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/timeline/{today}/",
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Services coverage
# ---------------------------------------------------------------------------


class TakeControlServiceTest(CoverageTestBase):
    def test_release_stale_locks(self):
        """services.py lines 296-299: release_stale_locks returns count."""
        from apps.clinicians.services import TakeControlService

        conv = AgentConversation.objects.create(
            patient=self.patient,
            agent_type="supervisor",
            status="active",
            paused_by=self.clin_user,
            paused_at=timezone.now() - timedelta(hours=2),
        )
        released = TakeControlService.release_stale_locks(timeout_minutes=30)
        assert released >= 1
        conv.refresh_from_db()
        assert conv.paused_by is None

    def test_release_stale_locks_none_expired(self):
        """services.py: no stale locks → returns 0."""
        from apps.clinicians.services import TakeControlService

        released = TakeControlService.release_stale_locks(timeout_minutes=30)
        assert released == 0

    def test_push_to_clinician_no_paused_by(self):
        """services.py line 339: push_to_clinician exits early when no paused_by."""
        from apps.clinicians.services import TakeControlService

        conv = AgentConversation.objects.create(
            patient=self.patient,
            agent_type="supervisor",
            status="active",
        )
        # Should not raise, just return early
        TakeControlService.push_to_clinician(conv, {"content": "test"})

    def test_push_to_clinician_channel_layer_unavailable(self):
        """services.py lines 339-353: channel layer exception handled gracefully."""
        from apps.clinicians.services import TakeControlService

        conv = AgentConversation.objects.create(
            patient=self.patient,
            agent_type="supervisor",
            status="active",
            paused_by=self.clin_user,
        )
        with patch("apps.clinicians.services.get_channel_layer", side_effect=Exception("no channel")):
            # Should not raise
            TakeControlService.push_to_clinician(conv, {"content": "test"})


class ClinicianResearchServiceTest(CoverageTestBase):
    def test_get_or_create_returns_existing(self):
        """services.py line 373: returns existing conversation."""
        from apps.clinicians.services import ClinicianResearchService

        existing = AgentConversation.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            agent_type="clinician_research",
            status="active",
        )
        result = ClinicianResearchService.get_or_create_research_conversation(self.patient, self.clinician)
        assert result.pk == existing.pk

    @patch("apps.clinicians.services.async_to_sync")
    @patch("apps.clinicians.services.ContextService.assemble_full_context")
    @patch("apps.clinicians.services.ConversationService.add_message")
    def test_send_research_message_llm_failure(self, mock_add_msg, mock_context, mock_async):
        """services.py lines 429-436: LLM failure falls back to error response."""
        from apps.clinicians.services import ClinicianResearchService

        # Simulate add_message returning a real object
        fake_conv = AgentConversation.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            agent_type="clinician_research",
            status="active",
        )
        fake_msg = AgentMessage.objects.create(
            conversation=fake_conv,
            role="assistant",
            agent_type="clinician_research",
            content="Research unavailable. Try again later.",
        )
        mock_add_msg.return_value = fake_msg
        mock_context.return_value = {}

        # Simulate workflow process_message raising
        mock_async.return_value = MagicMock(side_effect=Exception("LLM down"))

        result = ClinicianResearchService.send_research_message(self.patient, self.clinician, "test query")
        assert "response" in result

    def test_send_research_message_specialist_override(self):
        """services.py line 421: specialist_override is added to context."""
        from apps.clinicians.services import ClinicianResearchService

        with (
            patch.object(
                ClinicianResearchService,
                "send_research_message",
                wraps=ClinicianResearchService.send_research_message,
            ),
            patch("apps.clinicians.services.ContextService.assemble_full_context", return_value={}),
            patch("apps.clinicians.services.ConversationService.add_message") as mock_add,
        ):
            fake_conv = AgentConversation.objects.create(
                patient=self.patient,
                clinician=self.clinician,
                agent_type="clinician_research",
                status="active",
            )
            fake_msg = AgentMessage.objects.create(
                conversation=fake_conv,
                role="assistant",
                agent_type="clinician_research",
                content="Specialist answer.",
            )
            mock_add.return_value = fake_msg

            with patch("apps.clinicians.services.async_to_sync") as mock_a2s:
                mock_workflow = MagicMock()
                mock_workflow.process_message = MagicMock(
                    return_value={
                        "response": "Specialist answer.",
                        "agent_type": "orthopedic",
                        "escalate": False,
                        "metadata": {},
                    }
                )
                mock_a2s.return_value = lambda *a, **kw: {
                    "response": "Specialist answer.",
                    "agent_type": "orthopedic",
                    "escalate": False,
                    "metadata": {},
                }

                with patch("apps.agents.workflow.get_workflow", return_value=mock_workflow):
                    result = ClinicianResearchService.send_research_message(
                        self.patient,
                        self.clinician,
                        "test query",
                        specialist_override="orthopedic",
                    )
                    assert result is not None


class SchedulingServiceTest(CoverageTestBase):
    def test_get_available_slots_with_override(self):
        """services.py lines 517-523: one-off override replaces recurring windows."""
        from apps.clinicians.services import SchedulingService

        target_date = timezone.now().date() + timedelta(days=5)
        # Create a recurring window
        ClinicianAvailability.objects.create(
            clinician=self.clinician,
            day_of_week=target_date.weekday(),
            start_time="09:00",
            end_time="12:00",
            is_recurring=True,
        )
        # Create a one-off override that replaces it
        ClinicianAvailability.objects.create(
            clinician=self.clinician,
            day_of_week=target_date.weekday(),
            start_time="10:00",
            end_time="11:00",
            is_recurring=False,
            effective_date=target_date,
        )
        slots = SchedulingService.get_available_slots(self.clinician, target_date)
        # Override window is 1h; 30-min slots → 2 slots
        assert len(slots) == 2

    def test_get_available_slots_no_windows(self):
        """services.py lines 534-551: no availability windows → empty slots."""
        from apps.clinicians.services import SchedulingService

        # Use a date with no availability configured
        target_date = timezone.now().date() + timedelta(days=6)
        slots = SchedulingService.get_available_slots(self.clinician, target_date)
        assert slots == []

    def test_create_appointment_conflict_returns_none(self):
        """services.py line 583: conflict → returns None."""
        from apps.clinicians.services import SchedulingService

        start = timezone.now() + timedelta(days=7)
        end = start + timedelta(hours=1)
        # Pre-create a conflicting appointment
        Appointment.objects.create(
            clinician=self.clinician,
            patient=self.patient,
            scheduled_start=start,
            scheduled_end=end,
            appointment_type="follow_up",
            status="scheduled",
        )
        result = SchedulingService.create_appointment(
            clinician=self.clinician,
            patient=self.patient,
            start=start,
            end=end,
            appointment_type="check_in",
        )
        assert result is None


class PatientListServiceTest(CoverageTestBase):
    def test_get_status_line_fallback_no_annotations(self):
        """services.py lines 92-122: get_status_line fallback without annotations."""
        from apps.clinicians.services import PatientListService

        # Use a plain patient without annotations
        line = PatientListService.get_status_line(self.patient)
        assert isinstance(line, str)
        assert len(line) > 0

    def test_get_status_line_with_pending_escalation(self):
        """services.py line 99-100: pending escalation shown in status line."""
        from apps.clinicians.services import PatientListService

        Escalation.objects.create(
            patient=self.patient,
            reason="Urgent escalation reason",
            severity="urgent",
            status="pending",
        )
        # Remove annotations so fallback path is triggered
        patient = Patient.objects.get(pk=self.patient.pk)
        line = PatientListService.get_status_line(patient)
        assert "Urgent escalation reason" in line

    def test_get_status_line_with_last_message(self):
        """services.py lines 102-117: last_msg_content shown when no escalation."""
        from apps.clinicians.services import PatientListService

        conv = AgentConversation.objects.create(
            patient=self.patient,
            agent_type="supervisor",
            status="active",
        )
        AgentMessage.objects.create(
            conversation=conv,
            role="assistant",
            content="Last AI message content",
        )
        patient = Patient.objects.get(pk=self.patient.pk)
        line = PatientListService.get_status_line(patient)
        assert isinstance(line, str)


class HandoffServiceTest(CoverageTestBase):
    def test_get_handoff_summary(self):
        """services.py lines 139-172: handoff summary returns correct structure."""
        from apps.clinicians.services import HandoffService

        since = timezone.now() - timedelta(hours=8)
        summary = HandoffService.get_handoff_summary(self.clinician, since)
        assert "new_escalations" in summary
        assert "resolved_escalations" in summary
        assert "status_changes" in summary
        assert "new_escalation_count" in summary


# ---------------------------------------------------------------------------
# Pathway Assignment Views
# ---------------------------------------------------------------------------


class AssignPathwayViewTest(CoverageTestBase):
    """Tests for assign_pathway_view and unassign_pathway_view."""

    def setUp(self):
        super().setUp()
        from apps.pathways.models import ClinicalPathway

        self.pathway = ClinicalPathway.objects.create(
            name="Total Knee Recovery",
            surgery_type="Total Knee Replacement",
            description="Standard TKR recovery protocol",
            duration_days=90,
            is_active=True,
        )

    def test_assign_pathway_success(self):
        """Assigning a pathway creates PatientPathway record."""
        from apps.pathways.models import PatientPathway

        self.client.login(username=self.clin_user.username, password="testpass")  # pragma: allowlist secret
        resp = self.client.post(
            f"/clinician/patients/{self.patient.id}/assign-pathway/",
            {"pathway_id": self.pathway.id},
        )
        assert resp.status_code == 200
        assert PatientPathway.objects.filter(patient=self.patient, pathway=self.pathway, status="active").exists()

    def test_assign_pathway_replaces_existing(self):
        """Assigning a new pathway discontinues the previous one."""
        from apps.pathways.models import ClinicalPathway, PatientPathway

        PatientPathway.objects.create(patient=self.patient, pathway=self.pathway, status="active")
        new_pathway = ClinicalPathway.objects.create(
            name="Hip Recovery",
            surgery_type="Hip Replacement",
            description="Standard hip protocol",
            duration_days=60,
            is_active=True,
        )
        self.client.login(username=self.clin_user.username, password="testpass")  # pragma: allowlist secret
        resp = self.client.post(
            f"/clinician/patients/{self.patient.id}/assign-pathway/",
            {"pathway_id": new_pathway.id},
        )
        assert resp.status_code == 200
        old = PatientPathway.objects.get(patient=self.patient, pathway=self.pathway)
        assert old.status == "discontinued"
        assert PatientPathway.objects.filter(patient=self.patient, pathway=new_pathway, status="active").exists()

    def test_assign_pathway_missing_id(self):
        """Missing pathway_id returns 400."""
        self.client.login(username=self.clin_user.username, password="testpass")  # pragma: allowlist secret
        resp = self.client.post(
            f"/clinician/patients/{self.patient.id}/assign-pathway/",
            {},
        )
        assert resp.status_code == 400

    def test_assign_pathway_invalid_id(self):
        """Invalid pathway_id returns 400."""
        self.client.login(username=self.clin_user.username, password="testpass")  # pragma: allowlist secret
        resp = self.client.post(
            f"/clinician/patients/{self.patient.id}/assign-pathway/",
            {"pathway_id": 99999},
        )
        assert resp.status_code == 400

    def test_unassign_pathway_success(self):
        """Discontinuing an active pathway sets status to discontinued."""
        from apps.pathways.models import PatientPathway

        PatientPathway.objects.create(patient=self.patient, pathway=self.pathway, status="active")
        self.client.login(username=self.clin_user.username, password="testpass")  # pragma: allowlist secret
        resp = self.client.post(
            f"/clinician/patients/{self.patient.id}/unassign-pathway/",
        )
        assert resp.status_code == 200
        pp = PatientPathway.objects.get(patient=self.patient, pathway=self.pathway)
        assert pp.status == "discontinued"

    def test_unassign_pathway_none_active(self):
        """Discontinuing when no active pathway returns 400."""
        self.client.login(username=self.clin_user.username, password="testpass")  # pragma: allowlist secret
        resp = self.client.post(
            f"/clinician/patients/{self.patient.id}/unassign-pathway/",
        )
        assert resp.status_code == 400

    def test_tools_tab_shows_pathway_dropdown(self):
        """Tools tab includes pathway dropdown when pathways exist."""
        self.client.login(username=self.clin_user.username, password="testpass")  # pragma: allowlist secret
        resp = self.client.get(
            f"/clinician/patients/{self.patient.id}/tools/",
        )
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Total Knee Recovery" in content
        assert "assign-pathway" in content

    def test_tools_tab_shows_active_pathway(self):
        """Tools tab shows active pathway with discontinue button."""
        from apps.pathways.models import PatientPathway

        PatientPathway.objects.create(patient=self.patient, pathway=self.pathway, status="active")
        self.client.login(username=self.clin_user.username, password="testpass")  # pragma: allowlist secret
        resp = self.client.get(
            f"/clinician/patients/{self.patient.id}/tools/",
        )
        content = resp.content.decode()
        assert "Total Knee Recovery" in content
        assert "Discontinue" in content
