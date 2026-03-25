"""Tests for agent services."""

from unittest.mock import MagicMock, patch

from apps.agents.agents import calculate_confidence_score
from apps.agents.services import _notify_clinician_dashboard


class TestConfidenceScoring:
    """Tests for confidence scoring utility."""

    def test_high_confidence_with_stop_reason(self):
        """Test high confidence when LLM stops naturally."""
        score = calculate_confidence_score(
            "This is a detailed response with sufficient information.", "care_coordinator", llm_finish_reason="stop"
        )
        assert score >= 0.90
        assert score <= 1.0

    def test_low_confidence_short_response(self):
        """Test low confidence for very short responses."""
        score = calculate_confidence_score("Hi.", "care_coordinator")
        assert score < 0.75

    def test_confidence_penalty_for_critical_keywords(self):
        """Test confidence penalty when critical keywords present."""
        score = calculate_confidence_score("You have severe chest pain.", "nurse_triage", has_critical_keywords=True)
        # Should be reduced due to critical keywords
        assert score < 0.70

    def test_confidence_nurse_triage_adjustment(self):
        """Test nurse triage gets slight confidence reduction."""
        care_score = calculate_confidence_score("Everything looks good.", "care_coordinator")
        nurse_score = calculate_confidence_score("Everything looks good.", "nurse_triage")
        # Nurse triage should be slightly lower (more conservative)
        assert nurse_score <= care_score

    def test_confidence_bounds(self):
        """Test confidence is always between 0 and 1."""
        test_cases = [
            ("", "care_coordinator"),
            ("A" * 5000, "nurse_triage"),
            ("Normal response", "care_coordinator"),
        ]
        for response, agent_type in test_cases:
            score = calculate_confidence_score(response, agent_type)
            assert 0.0 <= score <= 1.0


class TestNotifyClinicianDashboard:
    """Tests for _notify_clinician_dashboard WebSocket broadcast."""

    @patch("apps.agents.services.get_channel_layer")
    def test_sends_patient_message_to_hospital_group(self, mock_get_layer):
        mock_layer = MagicMock()
        mock_layer.group_send = MagicMock()
        mock_get_layer.return_value = mock_layer

        patient = MagicMock()
        patient.hospital_id = 42
        patient.id = "abc-123"

        message_data = {"role": "user", "content": "hello"}
        _notify_clinician_dashboard(patient, message_data)

        mock_layer.group_send.assert_called_once()
        call_args = mock_layer.group_send.call_args
        assert call_args[0][0] == "hospital_42"
        payload = call_args[0][1]
        assert payload["type"] == "patient_message"
        assert payload["patient_id"] == "abc-123"
        assert payload["message"] == message_data

    @patch("apps.agents.services.get_channel_layer")
    def test_skips_when_no_hospital(self, mock_get_layer):
        patient = MagicMock()
        patient.hospital_id = None

        _notify_clinician_dashboard(patient, {"role": "user", "content": "hi"})

        mock_get_layer.assert_not_called()

    @patch("apps.agents.services.get_channel_layer", side_effect=Exception("no redis"))
    def test_handles_channel_layer_error_gracefully(self, mock_get_layer):
        patient = MagicMock()
        patient.hospital_id = 1
        patient.id = "xyz"

        # Should not raise
        _notify_clinician_dashboard(patient, {"role": "user", "content": "test"})
