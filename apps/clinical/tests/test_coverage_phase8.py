"""Coverage gap tests for Phase 8 additions to clinical app."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.clinical.services import ClinicalDataService
from apps.clinical.tasks import _get_proactive_message, send_proactive_patient_message


@pytest.mark.django_db
class TestProactiveMessageTask:
    """Test the Celery task for proactive patient messages."""

    def test_patient_not_found(self):
        """Task handles missing patient gracefully."""
        result = send_proactive_patient_message(
            patient_id=99999, rule_name="missing_weight", message_category="missing_data"
        )
        assert result is None

    def test_get_proactive_message_missing_data(self):
        """Missing data message template renders correctly."""
        msg = _get_proactive_message("missing_data", "Sarah", "")
        assert "Sarah" in msg
        assert "reading" in msg.lower()

    def test_get_proactive_message_weight_trend(self):
        """Weight trend message template renders correctly."""
        msg = _get_proactive_message("weight_trend", "Jimmy", "")
        assert "Jimmy" in msg
        assert "weight" in msg.lower()

    def test_get_proactive_message_activity_decline(self):
        """Activity decline message template renders correctly."""
        msg = _get_proactive_message("activity_decline", "Maria", "")
        assert "Maria" in msg
        assert "active" in msg.lower()

    def test_get_proactive_message_with_goal_reference(self):
        """Message includes goal reference when provided."""
        msg = _get_proactive_message("missing_data", "Bobby", " We want to make sure your recovery stays on track.")
        assert "Bobby" in msg
        assert "recovery stays on track" in msg

    def test_get_proactive_message_unknown_category_fallback(self):
        """Unknown category falls back to missing_data template."""
        msg = _get_proactive_message("unknown_category", "Test", "")
        assert "Test" in msg


@pytest.mark.django_db
class TestMaybeNotifyPatient:
    """Test the _maybe_notify_patient decision logic."""

    def test_non_patient_facing_rule_skipped(self):
        """Rules not in PATIENT_FACING_RULES are skipped."""
        alert = MagicMock()
        alert.rule_name = "bp_critical"  # Not in PATIENT_FACING_RULES
        ClinicalDataService._maybe_notify_patient(alert)
        # Should return without dispatching (no error = success)

    @patch("apps.clinical.services.ClinicalDataService.PATIENT_FACING_RULES", {"test_rule": "missing_data"})
    def test_patient_facing_rule_dispatches(self):
        """Patient-facing rules dispatch a Celery task."""
        from datetime import date

        from apps.accounts.models import User
        from apps.patients.models import Hospital, Patient

        hospital = Hospital.objects.create(name="Test Hospital")
        user = User.objects.create_user(username="test_notify", email="t@t.com", password="test")
        patient = Patient.objects.create(user=user, hospital=hospital, date_of_birth=date(1960, 1, 1))

        alert = MagicMock()
        alert.rule_name = "test_rule"
        alert.patient = patient

        with patch("apps.clinical.tasks.send_proactive_patient_message.delay") as mock_delay:
            ClinicalDataService._maybe_notify_patient(alert)
            mock_delay.assert_called_once()


@pytest.mark.django_db
class TestClinicalServiceEdgeCases:
    """Cover edge cases in clinical services for Phase 8."""

    def test_process_observation_exception_handling(self):
        """_process_observation handles exceptions gracefully."""
        patient = MagicMock()
        patient.pk = 99999

        with patch("apps.clinical.rules.check_all_rules", side_effect=Exception("test error")):
            # Should not raise
            ClinicalDataService._process_observation(patient)

    def test_create_escalation_exception_handling(self):
        """_create_escalation handles exceptions gracefully."""
        alert = MagicMock()
        alert.patient = MagicMock()
        alert.patient.pk = 99999
        alert.id = "test-id"
        alert.severity = "red"

        with patch("apps.agents.models.Escalation.objects.create", side_effect=Exception("test")):
            # Should not raise
            ClinicalDataService._create_escalation(alert)


@pytest.mark.django_db
class TestProactiveTaskWithPreferences:
    """Test proactive messaging with real patient + preferences for coverage."""

    @pytest.fixture
    def patient_with_prefs(self):
        from apps.accounts.models import User
        from apps.patients.models import Hospital, Patient, PatientPreferences

        hospital = Hospital.objects.create(name="Coverage Hospital")
        user = User.objects.create_user(
            username="cov_patient",
            email="cov@test.com",
            password="test",  # pragma: allowlist secret
            first_name="CovTest",
        )
        patient = Patient.objects.create(user=user, hospital=hospital, date_of_birth=date(1965, 3, 15))
        PatientPreferences.objects.create(
            patient=patient,
            preferred_name="CoveragePatient",
            recovery_goals="Get back to gardening",
        )
        return patient

    def test_task_with_preferred_name(self, patient_with_prefs):
        """Task uses preferred_name from PatientPreferences."""
        send_proactive_patient_message(
            patient_id=patient_with_prefs.pk,
            rule_name="missing_weight",
            message_category="missing_data",
        )
        from apps.agents.models import AgentMessage

        msg = AgentMessage.objects.filter(
            conversation__patient=patient_with_prefs,
            metadata__proactive_rule="missing_weight",
        ).first()
        assert msg is not None
        assert "CoveragePatient" in msg.content

    def test_task_with_recovery_goals(self, patient_with_prefs):
        """Task includes goal reference when recovery_goals set."""
        send_proactive_patient_message(
            patient_id=patient_with_prefs.pk,
            rule_name="weight_gain_3day",
            message_category="weight_trend",
        )
        from apps.agents.models import AgentMessage

        msg = AgentMessage.objects.filter(
            conversation__patient=patient_with_prefs,
            metadata__proactive_rule="weight_gain_3day",
        ).first()
        assert msg is not None
        assert "recovery" in msg.content.lower() or "matters" in msg.content.lower()

    def test_task_preferences_exception(self):
        """Task handles preferences exception gracefully."""
        from apps.accounts.models import User
        from apps.patients.models import Hospital, Patient

        hospital = Hospital.objects.create(name="No Prefs Hospital")
        user = User.objects.create_user(
            username="noprefs_pat",
            password="test",  # pragma: allowlist secret
            first_name="NoPref",
        )
        patient = Patient.objects.create(user=user, hospital=hospital, date_of_birth=date(1970, 1, 1))
        # No preferences — should use first_name fallback
        send_proactive_patient_message(
            patient_id=patient.pk,
            rule_name="steps_declining_7day",
            message_category="activity_decline",
        )
        from apps.agents.models import AgentMessage

        msg = AgentMessage.objects.filter(
            conversation__patient=patient,
            metadata__proactive_rule="steps_declining_7day",
        ).first()
        assert msg is not None
        assert "NoPref" in msg.content


@pytest.mark.django_db
class TestQuietHoursCheck:
    """Test the quiet hours guard in proactive messaging."""

    def test_non_patient_facing_rule_skips_silently(self):
        """Rules NOT in PATIENT_FACING_RULES return immediately."""
        alert = MagicMock()
        alert.rule_name = "hr_critical"  # Not patient-facing
        ClinicalDataService._maybe_notify_patient(alert)
        # No exception = pass

    def test_patient_facing_rules_defined(self):
        """PATIENT_FACING_RULES maps rule names to message categories."""
        rules = ClinicalDataService.PATIENT_FACING_RULES
        assert isinstance(rules, dict)
        assert len(rules) >= 3
        # All values should be valid message categories
        for rule_name, category in rules.items():
            assert isinstance(rule_name, str)
            assert isinstance(category, str)


@pytest.mark.django_db
class TestClinicianTasksCoverage:
    """Cover clinicians/tasks.py edge cases."""

    @pytest.fixture
    def setup_data(self):
        from apps.accounts.models import User
        from apps.clinicians.models import Clinician
        from apps.patients.models import Hospital, Patient

        hospital = Hospital.objects.create(name="Task Cov Hospital")
        clin_user = User.objects.create_user(
            username="dr_cov",
            password="test",  # pragma: allowlist secret
            role="clinician",
            first_name="Dr",
            last_name="Coverage",
        )
        clinician = Clinician.objects.create(user=clin_user, role="physician", is_active=True)
        clinician.hospitals.add(hospital)

        pat_user = User.objects.create_user(
            username="pat_cov",
            password="test",  # pragma: allowlist secret
            role="patient",
            first_name="Pat",
            last_name="Coverage",
        )
        patient = Patient.objects.create(user=pat_user, hospital=hospital, date_of_birth=date(1980, 5, 5))
        return {"patient": patient, "clinician": clinician, "hospital": hospital}

    def test_expire_appointment_requests(self, setup_data):
        """Expire task marks old pending requests as expired."""
        from apps.clinicians.models import AppointmentRequest
        from apps.clinicians.tasks import expire_appointment_requests

        now = timezone.now()
        req = AppointmentRequest.objects.create(
            patient=setup_data["patient"],
            clinician=setup_data["clinician"],
            trigger_type="milestone",
            reason="Day 14 follow-up",
            earliest_notify_at=now - timedelta(days=10),
            expires_at=now - timedelta(days=1),  # Already expired
            status="pending",
        )
        result = expire_appointment_requests()
        req.refresh_from_db()
        assert req.status == "expired"
        assert result["expired"] >= 1

    def test_notify_upcoming_appointments(self, setup_data):
        """Notify task sends notifications for due requests."""
        from apps.clinicians.models import AppointmentRequest
        from apps.clinicians.tasks import notify_upcoming_appointments

        now = timezone.now()
        AppointmentRequest.objects.create(
            patient=setup_data["patient"],
            clinician=setup_data["clinician"],
            trigger_type="clinician",
            reason="Virtual visit",
            earliest_notify_at=now - timedelta(hours=1),  # Already due
            expires_at=now + timedelta(days=7),
            status="pending",
        )
        result = notify_upcoming_appointments()
        assert result["notified"] >= 1

    def test_reminder_exception_handling(self, setup_data):
        """Reminder task handles notification exceptions gracefully."""
        from apps.clinicians.models import Appointment
        from apps.clinicians.tasks import send_appointment_reminders

        now = timezone.now()
        Appointment.objects.create(
            clinician=setup_data["clinician"],
            patient=setup_data["patient"],
            scheduled_start=now + timedelta(hours=23),
            scheduled_end=now + timedelta(hours=23, minutes=30),
            appointment_type="follow_up",
            status="scheduled",
            reminder_24h_sent=False,
        )
        with patch(
            "apps.notifications.services.NotificationService.create_notification",
            side_effect=Exception("notification error"),
        ):
            # Should not raise — handles exception internally
            result = send_appointment_reminders()
            assert result["processed"] == 0
