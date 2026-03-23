"""Tests for proactive patient messaging — _maybe_notify_patient() and send_proactive_patient_message task."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.agents.models import AgentMessage
from apps.agents.tests.factories import PatientFactory
from apps.clinical.models import ClinicalAlert
from apps.clinical.services import ClinicalDataService
from apps.clinical.tasks import send_proactive_patient_message
from apps.patients.models import PatientPreferences


@pytest.fixture
def patient(db):
    return PatientFactory(user__first_name="Maria")


@pytest.fixture
def patient_with_prefs(patient):
    PatientPreferences.objects.create(
        patient=patient,
        preferred_name="Mari",
        recovery_goals="Get back to gardening",
    )
    return patient


@pytest.fixture
def patient_facing_alert(patient):
    """Create a patient-facing alert (missing_weight)."""
    return ClinicalAlert.objects.create(
        patient=patient,
        alert_type="trend",
        severity="yellow",
        rule_name="missing_weight",
        title="Missing weight data",
        description="No weight readings in 48 hours",
    )


@pytest.fixture
def non_patient_facing_alert(patient):
    """Create a non-patient-facing alert (bp_critical)."""
    return ClinicalAlert.objects.create(
        patient=patient,
        alert_type="threshold",
        severity="red",
        rule_name="bp_critical",
        title="Critical blood pressure",
        description="Blood pressure critically high",
    )


class TestMaybeNotifyPatient:
    def test_notify_patient_missing_weight_rule(self, patient, patient_facing_alert):
        """missing_weight alert triggers proactive patient message."""
        ClinicalDataService._maybe_notify_patient(patient_facing_alert)
        msg = AgentMessage.objects.filter(
            conversation__patient=patient,
            metadata__proactive_rule="missing_weight",
        ).first()
        assert msg is not None
        assert msg.role == "assistant"
        assert msg.agent_type == "care_coordinator"

    def test_notify_patient_weight_gain_rule(self, patient):
        """weight_gain_3day alert triggers proactive patient message."""
        alert = ClinicalAlert.objects.create(
            patient=patient,
            alert_type="trend",
            severity="yellow",
            rule_name="weight_gain_3day",
            title="Weight gain trend",
            description="Weight increasing over 3 days",
        )
        ClinicalDataService._maybe_notify_patient(alert)
        assert AgentMessage.objects.filter(
            conversation__patient=patient,
            metadata__proactive_rule="weight_gain_3day",
        ).exists()

    def test_notify_patient_activity_decline(self, patient):
        """steps_declining_7day alert triggers proactive patient message."""
        alert = ClinicalAlert.objects.create(
            patient=patient,
            alert_type="trend",
            severity="yellow",
            rule_name="steps_declining_7day",
            title="Activity declining",
            description="Step count declining over 7 days",
        )
        ClinicalDataService._maybe_notify_patient(alert)
        assert AgentMessage.objects.filter(
            conversation__patient=patient,
            metadata__proactive_rule="steps_declining_7day",
        ).exists()

    def test_non_patient_facing_rule_no_message(self, patient, non_patient_facing_alert):
        """bp_critical is not in PATIENT_FACING_RULES — no message should be sent."""
        ClinicalDataService._maybe_notify_patient(non_patient_facing_alert)
        assert not AgentMessage.objects.filter(
            conversation__patient=patient,
            metadata__has_key="proactive_rule",
        ).exists()

    def test_dedup_within_24h(self, patient, patient_facing_alert):
        """Same rule within 24h does not send a duplicate message."""
        ClinicalDataService._maybe_notify_patient(patient_facing_alert)
        initial_count = AgentMessage.objects.filter(
            conversation__patient=patient,
            metadata__proactive_rule="missing_weight",
        ).count()
        assert initial_count == 1

        # Second call — should be deduped
        ClinicalDataService._maybe_notify_patient(patient_facing_alert)
        assert (
            AgentMessage.objects.filter(
                conversation__patient=patient,
                metadata__proactive_rule="missing_weight",
            ).count()
            == 1
        )

    def test_dedup_allows_after_24h(self, patient):
        """Same rule after 24h allows a new message."""
        alert = ClinicalAlert.objects.create(
            patient=patient,
            alert_type="trend",
            severity="yellow",
            rule_name="missing_weight",
            title="Missing weight",
            description="No weight readings",
        )
        # Send first message
        ClinicalDataService._maybe_notify_patient(alert)
        assert AgentMessage.objects.filter(metadata__proactive_rule="missing_weight").count() == 1

        # Backdate the existing message to >24h ago
        AgentMessage.objects.filter(metadata__proactive_rule="missing_weight").update(
            created_at=timezone.now() - timedelta(hours=25)
        )

        # Second call — should send because >24h
        ClinicalDataService._maybe_notify_patient(alert)
        assert AgentMessage.objects.filter(metadata__proactive_rule="missing_weight").count() == 2


class TestSendProactivePatientMessage:
    def test_message_uses_preferred_name(self, patient_with_prefs):
        """Message references patient's preferred_name from preferences."""
        send_proactive_patient_message(
            patient_id=patient_with_prefs.pk,
            rule_name="missing_weight",
            message_category="missing_data",
        )
        msg = AgentMessage.objects.filter(
            conversation__patient=patient_with_prefs,
        ).first()
        assert msg is not None
        assert "Mari" in msg.content

    def test_message_includes_goal_reference(self, patient_with_prefs):
        """When recovery_goals are set, message includes goal reference."""
        send_proactive_patient_message(
            patient_id=patient_with_prefs.pk,
            rule_name="missing_weight",
            message_category="missing_data",
        )
        msg = AgentMessage.objects.filter(
            conversation__patient=patient_with_prefs,
        ).first()
        assert msg is not None
        # Goal reference text from the task
        assert "what matters to you" in msg.content.lower() or "recovery" in msg.content.lower()

    def test_proactive_message_creates_agent_message(self, patient):
        """Verify AgentMessage is created with proactive_rule metadata."""
        send_proactive_patient_message(
            patient_id=patient.pk,
            rule_name="steps_declining_7day",
            message_category="activity_decline",
        )
        msg = AgentMessage.objects.filter(
            conversation__patient=patient,
        ).first()
        assert msg is not None
        assert msg.metadata["proactive_rule"] == "steps_declining_7day"
        assert msg.metadata["proactive_category"] == "activity_decline"
        assert msg.role == "assistant"
        assert msg.agent_type == "care_coordinator"

    def test_message_falls_back_to_first_name(self, patient):
        """Without preferences, uses user.first_name as preferred name."""
        send_proactive_patient_message(
            patient_id=patient.pk,
            rule_name="missing_weight",
            message_category="missing_data",
        )
        msg = AgentMessage.objects.filter(conversation__patient=patient).first()
        assert msg is not None
        assert "Maria" in msg.content
