"""Tests for patient template tags."""

from apps.patients.templatetags.patient_tags import agent_display_name, agent_icon


class TestAgentDisplayName:
    """Test agent_display_name filter."""

    def test_care_coordinator(self):
        assert agent_display_name("care_coordinator") == "Care Coordinator"

    def test_nurse_triage(self):
        assert agent_display_name("nurse_triage") == "Nurse"

    def test_supervisor(self):
        assert agent_display_name("supervisor") == "Clintela"

    def test_documentation(self):
        assert agent_display_name("documentation") == "Documentation"

    def test_escalation(self):
        assert agent_display_name("escalation") == "Clintela"

    def test_unknown_returns_assistant(self):
        assert agent_display_name("unknown") == "Assistant"

    def test_empty_string_returns_assistant(self):
        assert agent_display_name("") == "Assistant"

    def test_specialist(self):
        assert agent_display_name("specialist_cardiology") == "Cardiology Specialist"


class TestAgentIcon:
    """Test agent_icon filter."""

    def test_care_coordinator(self):
        assert agent_icon("care_coordinator") == "heart-handshake"

    def test_nurse_triage(self):
        assert agent_icon("nurse_triage") == "stethoscope"

    def test_supervisor(self):
        assert agent_icon("supervisor") == "bot"

    def test_unknown_returns_bot(self):
        assert agent_icon("unknown") == "bot"

    def test_empty_string_returns_bot(self):
        assert agent_icon("") == "bot"
