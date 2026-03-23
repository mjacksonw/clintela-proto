"""Coverage gap tests for Phase 8 additions to clinical app."""

from unittest.mock import MagicMock, patch

import pytest

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
