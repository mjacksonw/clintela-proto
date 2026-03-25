"""Tests for clinician views."""

import uuid as _uuid

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.agents.models import AgentConversation, AgentMessage, Escalation
from apps.clinicians.models import Appointment, Clinician, ClinicianNote
from apps.patients.models import Hospital, Patient

_DOB = "1960-01-15"


def _code():
    return f"TST-{_uuid.uuid4().hex[:8]}"


def _lc():
    return f"LC-{_uuid.uuid4().hex[:8]}"


class ViewTestBase(TestCase):
    """Base test class with common setup."""

    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test Hospital", code=_code())
        self.clin_user = User.objects.create_user(
            username="dr_views",
            password="testpass",  # pragma: allowlist secret
            role="clinician",
            first_name="View",
            last_name="Doctor",
        )
        self.clinician = Clinician.objects.create(
            user=self.clin_user,
            role="physician",
            is_active=True,
        )
        self.clinician.hospitals.add(self.hospital)

        self.pat_user = User.objects.create_user(
            username="pat_views",
            password="testpass",  # pragma: allowlist secret
            role="patient",
            first_name="View",
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
        self.client.login(username="dr_views", password="testpass")  # pragma: allowlist secret


class DashboardViewTest(ViewTestBase):
    def test_dashboard_renders(self):
        response = self.client.get("/clinician/dashboard/")
        assert response.status_code == 200
        assert b"Clintela" in response.content

    def test_dashboard_first_login(self):
        self.clin_user.last_login = None
        self.clin_user.save()
        response = self.client.get("/clinician/dashboard/")
        assert response.status_code == 200
        assert b"Welcome" in response.content

    def test_dashboard_requires_auth(self):
        self.client.logout()
        response = self.client.get("/clinician/dashboard/")
        assert response.status_code == 302


class DashboardUrlRoutingTest(ViewTestBase):
    """Tests for path-based URL routing deep links."""

    def test_dashboard_with_valid_patient(self):
        response = self.client.get(f"/clinician/dashboard/patient/{self.patient.id}/")
        assert response.status_code == 200
        assert response.context["initial_patient_id"] == self.patient.id
        assert response.context["initial_tab"] == "details"
        assert response.context["initial_subview"] is None

    def test_dashboard_with_valid_patient_and_tab(self):
        response = self.client.get(f"/clinician/dashboard/patient/{self.patient.id}/surveys/")
        assert response.status_code == 200
        assert response.context["initial_patient_id"] == self.patient.id
        assert response.context["initial_tab"] == "surveys"

    def test_dashboard_with_valid_patient_tab_and_subview(self):
        response = self.client.get(
            f"/clinician/dashboard/patient/{self.patient.id}/surveys/some-uuid/"
        )
        assert response.status_code == 200
        assert response.context["initial_patient_id"] == self.patient.id
        assert response.context["initial_tab"] == "surveys"
        assert response.context["initial_subview"] == "some-uuid"

    def test_dashboard_with_nonexistent_patient(self):
        response = self.client.get("/clinician/dashboard/patient/99999/")
        assert response.status_code == 200
        assert response.context["initial_patient_id"] is None

    def test_dashboard_with_unauthorized_patient(self):
        """Patient from a different hospital should not be accessible."""
        other_hospital = Hospital.objects.create(name="Other Hospital", code=_code())
        other_pat_user = User.objects.create_user(
            username="pat_other", password="testpass", role="patient"  # pragma: allowlist secret
        )
        other_patient = Patient.objects.create(
            user=other_pat_user,
            hospital=other_hospital,
            status="green",
            lifecycle_status="post_op",
            surgery_type="Hip Replacement",
            date_of_birth=_DOB,
            leaflet_code=_lc(),
        )
        response = self.client.get(f"/clinician/dashboard/patient/{other_patient.id}/")
        assert response.status_code == 200
        assert response.context["initial_patient_id"] is None

    def test_dashboard_with_invalid_tab(self):
        response = self.client.get(f"/clinician/dashboard/patient/{self.patient.id}/bogus/")
        assert response.status_code == 200
        assert response.context["initial_patient_id"] == self.patient.id
        assert response.context["initial_tab"] == "details"

    def test_dashboard_surveys_tab_button_rendered(self):
        response = self.client.get("/clinician/dashboard/")
        content = response.content.decode()
        assert "switchTab('surveys')" in content


class AppointmentToastLayoutTest(ViewTestBase):
    """Next-appointment toast must not use fixed positioning (would overlap chat input)."""

    def test_toast_not_fixed_when_appointment_exists(self):
        """Toast renders as a flex item, not a fixed overlay."""
        now = timezone.now()
        Appointment.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            created_by=self.clin_user,
            appointment_type="virtual_visit",
            status="scheduled",
            scheduled_start=now + timezone.timedelta(hours=1),
            scheduled_end=now + timezone.timedelta(hours=2),
        )
        response = self.client.get("/clinician/dashboard/")
        content = response.content.decode()

        # Toast should appear with appointment info
        assert "Virtual Visit" in content
        # Toast must be a flex item (not fixed) — fixed positioning overlaps chat input
        # Extract the toast's <div> class attribute and verify no "fixed" positioning
        toast_start = content.find("Footer toast: next appointment")
        assert toast_start != -1, "Toast comment not found in output"
        # Find the <div class="..." after the comment
        div_start = content.find('class="', toast_start)
        div_end = content.find('"', div_start + 7)
        toast_classes = content[div_start + 7 : div_end]
        assert "fixed" not in toast_classes, f"Toast still uses fixed positioning: {toast_classes}"
        assert "flex-shrink-0" in toast_classes, "Toast should be a flex-shrink-0 layout item"

    def test_toast_hidden_when_no_appointment(self):
        """No toast rendered when there is no upcoming appointment."""
        response = self.client.get("/clinician/dashboard/")
        content = response.content.decode()
        assert "next_appointment_toast" not in content
        assert "calendar" not in content or b"Next:" not in response.content


class PatientListFragmentTest(ViewTestBase):
    def test_patient_list_loads(self):
        response = self.client.get("/clinician/patients/")
        assert response.status_code == 200
        assert b"View Patient" in response.content

    def test_patient_list_search(self):
        response = self.client.get("/clinician/patients/?search=View")
        assert response.status_code == 200
        assert b"View Patient" in response.content

    def test_patient_list_search_no_results(self):
        response = self.client.get("/clinician/patients/?search=ZZZZZ")
        assert response.status_code == 200
        assert b"No patients match" in response.content

    def test_patient_list_sort_alpha(self):
        response = self.client.get("/clinician/patients/?sort=alpha")
        assert response.status_code == 200

    def test_patient_list_sort_last_contact(self):
        response = self.client.get("/clinician/patients/?sort=last_contact")
        assert response.status_code == 200


class PatientDetailTabsTest(ViewTestBase):
    def test_details_tab(self):
        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/detail/",
        )
        assert response.status_code == 200
        assert b"View Patient" in response.content

    def test_care_plan_tab(self):
        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/care-plan/",
        )
        assert response.status_code == 200

    def test_research_tab(self):
        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/research/",
        )
        assert response.status_code == 200
        assert b"Research" in response.content

    def test_tools_tab(self):
        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/tools/",
        )
        assert response.status_code == 200

    def test_idor_rejected(self):
        """Patient from different hospital should be rejected."""
        other_hospital = Hospital.objects.create(name="Other", code=_code())
        other_user = User.objects.create_user(
            username="idor_pat",
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
        response = self.client.get(
            f"/clinician/patients/{other_patient.id}/detail/",
        )
        assert response.status_code == 403


class PatientChatFragmentTest(ViewTestBase):
    def test_chat_no_conversation(self):
        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/chat/",
        )
        assert response.status_code == 200
        assert b"No conversation" in response.content

    def test_chat_with_conversation(self):
        conv = AgentConversation.objects.create(
            patient=self.patient,
            agent_type="supervisor",
            status="active",
        )
        AgentMessage.objects.create(
            conversation=conv,
            role="user",
            content="Hello",
        )
        AgentMessage.objects.create(
            conversation=conv,
            role="assistant",
            agent_type="care_coordinator",
            content="Hi there!",
        )
        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/chat/",
        )
        assert response.status_code == 200
        assert b"Hello" in response.content


class InjectMessageTest(ViewTestBase):
    def test_inject_creates_message(self):
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/inject-message/",
            {"message": "Test clinician message"},
        )
        assert response.status_code == 200
        msg = AgentMessage.objects.filter(agent_type="clinician").first()
        assert msg is not None
        assert msg.content == "Test clinician message"

    def test_inject_takes_control(self):
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/inject-message/",
            {"message": "Taking over"},
        )
        assert response.status_code == 200
        conv = AgentConversation.objects.filter(patient=self.patient).first()
        assert conv.paused_by == self.clin_user

    def test_inject_empty_message_rejected(self):
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/inject-message/",
            {"message": ""},
        )
        assert response.status_code == 400

    def test_inject_race_condition(self):
        """Second clinician cannot inject when first has control."""
        # First clinician takes control
        self.client.post(
            f"/clinician/patients/{self.patient.id}/inject-message/",
            {"message": "First"},
        )

        # Second clinician tries
        other_user = User.objects.create_user(
            username="dr_other",
            password="testpass",  # pragma: allowlist secret
            role="clinician",
        )
        other_clin = Clinician.objects.create(
            user=other_user,
            role="physician",
            is_active=True,
        )
        other_clin.hospitals.add(self.hospital)

        self.client.login(username="dr_other", password="testpass")  # pragma: allowlist secret
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/inject-message/",
            {"message": "Second"},
        )
        assert response.status_code == 200
        assert b"currently responding" in response.content


class ReleaseControlTest(ViewTestBase):
    def test_release_control(self):
        # Take control first
        self.client.post(
            f"/clinician/patients/{self.patient.id}/inject-message/",
            {"message": "Hi"},
        )
        conv = AgentConversation.objects.filter(patient=self.patient).first()
        assert conv.paused_by is not None

        # Release
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/take-control/release/",
        )
        assert response.status_code == 200
        conv.refresh_from_db()
        assert conv.paused_by is None


class NotesViewTest(ViewTestBase):
    def test_add_note(self):
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/notes/add/",
            {"content": "Test note", "note_type": "quick_note"},
        )
        assert response.status_code == 200
        assert ClinicianNote.objects.filter(patient=self.patient).count() == 1

    def test_add_empty_note_rejected(self):
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/notes/add/",
            {"content": "", "note_type": "quick_note"},
        )
        assert response.status_code == 400


class EscalationViewTest(ViewTestBase):
    def setUp(self):
        super().setUp()
        self.escalation = Escalation.objects.create(
            patient=self.patient,
            reason="Test escalation",
            severity="urgent",
            status="pending",
        )

    def test_acknowledge(self):
        response = self.client.post(
            f"/clinician/escalations/{self.escalation.id}/acknowledge/",
        )
        assert response.status_code == 200
        self.escalation.refresh_from_db()
        assert self.escalation.status == "acknowledged"

    def test_resolve(self):
        response = self.client.post(
            f"/clinician/escalations/{self.escalation.id}/resolve/",
        )
        assert response.status_code == 200
        self.escalation.refresh_from_db()
        assert self.escalation.status == "resolved"

    def test_bulk_acknowledge(self):
        esc2 = Escalation.objects.create(
            patient=self.patient,
            reason="Second",
            severity="routine",
            status="pending",
        )
        response = self.client.post(
            "/clinician/escalations/bulk-acknowledge/",
            {"escalation_ids": [str(self.escalation.id), str(esc2.id)]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["acknowledged"] == 2

    def test_escalation_idor(self):
        """Escalation for patient in different hospital should be rejected."""
        other_hospital = Hospital.objects.create(name="Other", code=_code())
        other_user = User.objects.create_user(
            username="idor_esc_pat",
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
        other_esc = Escalation.objects.create(
            patient=other_patient,
            reason="Other",
            severity="routine",
            status="pending",
        )
        response = self.client.post(
            f"/clinician/escalations/{other_esc.id}/acknowledge/",
        )
        assert response.status_code == 403


class LifecycleTransitionTest(ViewTestBase):
    def test_valid_transition(self):
        self.patient.lifecycle_status = "post_op"
        self.patient.save()
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/lifecycle/",
            {"new_status": "discharged"},
        )
        assert response.status_code == 200

    def test_invalid_transition(self):
        self.patient.lifecycle_status = "pre_surgery"
        self.patient.save()
        response = self.client.post(
            f"/clinician/patients/{self.patient.id}/lifecycle/",
            {"new_status": "recovered"},
        )
        assert response.status_code == 400


class ScheduleViewTest(ViewTestBase):
    def test_schedule_renders(self):
        response = self.client.get("/clinician/schedule/")
        assert response.status_code == 200
        assert b"Schedule" in response.content

    def test_schedule_week_navigation(self):
        response = self.client.get("/clinician/schedule/?week_offset=1")
        assert response.status_code == 200


class ExportHandoffTest(ViewTestBase):
    def test_export_handoff_json(self):
        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/export-handoff/",
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"


class TimelineDayTest(ViewTestBase):
    def test_timeline_day_empty(self):
        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/timeline/2026-03-20/",
        )
        assert response.status_code == 200

    def test_timeline_day_invalid_date(self):
        response = self.client.get(
            f"/clinician/patients/{self.patient.id}/timeline/invalid/",
        )
        assert response.status_code == 400
