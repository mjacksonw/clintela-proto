"""Comprehensive tests for agent services."""

import uuid
from datetime import date, timedelta

import pytest

from apps.agents.models import AgentConversation
from apps.agents.services import ContextService, ConversationService, EscalationService
from apps.agents.tests.factories import (
    AgentConversationFactory,
    AgentMessageFactory,
    ConversationStateFactory,
    EscalationFactory,
    HospitalFactory,
    PatientFactory,
    UserFactory,
)
from apps.pathways.models import ClinicalPathway, PathwayMilestone, PatientPathway


@pytest.mark.django_db
class TestConversationService:
    """Tests for ConversationService."""

    def test_get_or_create_conversation_creates_new(self):
        """Test creating a new conversation when none exists."""
        patient = PatientFactory()

        conversation = ConversationService.get_or_create_conversation(patient, agent_type="supervisor")

        assert conversation.patient == patient
        assert conversation.status == "active"
        assert conversation.agent_type == "supervisor"
        assert conversation.context == {}

        # Verify state was created
        assert hasattr(conversation, "state")
        assert conversation.state.patient_summary == f"{patient.user.first_name} {patient.user.last_name}"

    def test_get_or_create_conversation_returns_existing_active(self):
        """Test returning existing active conversation."""
        patient = PatientFactory()
        existing_conversation = AgentConversationFactory(patient=patient, status="active")

        conversation = ConversationService.get_or_create_conversation(patient)

        assert conversation.id == existing_conversation.id
        assert AgentConversation.objects.filter(patient=patient).count() == 1

    def test_get_or_create_conversation_creates_when_no_active(self):
        """Test creating new when existing is not active."""
        patient = PatientFactory()
        AgentConversationFactory(patient=patient, status="completed")
        AgentConversationFactory(patient=patient, status="escalated")

        conversation = ConversationService.get_or_create_conversation(patient, agent_type="care_coordinator")

        assert conversation.status == "active"
        assert conversation.agent_type == "care_coordinator"
        assert AgentConversation.objects.filter(patient=patient).count() == 3

    def test_get_or_create_conversation_different_agent_types(self):
        """Test creating conversations with different agent types."""
        patient = PatientFactory()

        conv1 = ConversationService.get_or_create_conversation(patient, agent_type="supervisor")
        conv1.status = "completed"
        conv1.save()

        conv2 = ConversationService.get_or_create_conversation(patient, agent_type="nurse_triage")

        assert conv2.agent_type == "nurse_triage"

    def test_add_message_with_all_fields(self):
        """Test adding message with all optional fields."""
        conversation = AgentConversationFactory()
        metadata = {"key": "value", "nested": {"data": 123}}

        message = ConversationService.add_message(
            conversation=conversation,
            role="assistant",
            content="Test message content",
            agent_type="care_coordinator",
            routing_decision="route_to_specialist",
            confidence_score=0.95,
            escalation_triggered=True,
            escalation_reason="High severity symptom reported",
            metadata=metadata,
        )

        assert message.conversation == conversation
        assert message.role == "assistant"
        assert message.content == "Test message content"
        assert message.agent_type == "care_coordinator"
        assert message.routing_decision == "route_to_specialist"
        assert message.confidence_score == 0.95
        assert message.escalation_triggered is True
        assert message.escalation_reason == "High severity symptom reported"
        assert message.metadata == metadata

    def test_add_message_with_defaults(self):
        """Test adding message with minimal fields."""
        conversation = AgentConversationFactory()

        message = ConversationService.add_message(
            conversation=conversation,
            role="user",
            content="Hello",
        )

        assert message.conversation == conversation
        assert message.role == "user"
        assert message.content == "Hello"
        assert message.agent_type == ""
        assert message.routing_decision == ""
        assert message.confidence_score is None
        assert message.escalation_triggered is False
        assert message.escalation_reason == ""
        assert message.metadata == {}

    def test_add_message_with_none_metadata(self):
        """Test adding message with None metadata defaults to empty dict."""
        conversation = AgentConversationFactory()

        message = ConversationService.add_message(
            conversation=conversation,
            role="user",
            content="Test",
            metadata=None,
        )

        assert message.metadata == {}

    def test_get_conversation_history(self):
        """Test getting conversation history."""
        conversation = AgentConversationFactory()

        # Create messages in chronological order
        AgentMessageFactory(conversation=conversation, role="user", content="Hello")  # noqa: F841
        AgentMessageFactory(conversation=conversation, role="assistant", content="Hi there")  # noqa: F841
        AgentMessageFactory(conversation=conversation, role="user", content="I have pain")  # noqa: F841

        history = ConversationService.get_conversation_history(conversation, limit=10)

        assert len(history) == 3
        # Should be returned oldest first
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[2]["content"] == "I have pain"
        assert "created_at" in history[0]
        assert "agent_type" in history[0]

    def test_get_conversation_history_with_limit(self):
        """Test history respects limit parameter."""
        conversation = AgentConversationFactory()

        for i in range(15):
            AgentMessageFactory(conversation=conversation, content=f"Message {i}")

        history = ConversationService.get_conversation_history(conversation, limit=5)

        assert len(history) == 5

    def test_get_conversation_history_empty(self):
        """Test getting history for conversation with no messages."""
        conversation = AgentConversationFactory()

        history = ConversationService.get_conversation_history(conversation)

        assert history == []

    def test_get_conversation_history_different_conversations(self):
        """Test history only returns messages for specified conversation."""
        conv1 = AgentConversationFactory()
        conv2 = AgentConversationFactory()

        AgentMessageFactory(conversation=conv1, content="Conv1 message")
        AgentMessageFactory(conversation=conv2, content="Conv2 message")

        history = ConversationService.get_conversation_history(conv1)

        assert len(history) == 1
        assert history[0]["content"] == "Conv1 message"

    def test_update_conversation_status(self):
        """Test updating conversation status."""
        conversation = AgentConversationFactory(status="active")

        ConversationService.update_conversation_status(conversation, "escalated")

        conversation.refresh_from_db()
        assert conversation.status == "escalated"
        assert conversation.escalation_reason == ""

    def test_update_conversation_status_with_escalation_reason(self):
        """Test updating status with escalation reason."""
        conversation = AgentConversationFactory(status="active")

        ConversationService.update_conversation_status(conversation, "escalated", escalation_reason="Critical symptom")

        conversation.refresh_from_db()
        assert conversation.status == "escalated"
        assert conversation.escalation_reason == "Critical symptom"

    def test_update_conversation_status_all_statuses(self):
        """Test updating to various statuses."""
        conversation = AgentConversationFactory(status="active")

        for status in ["paused", "completed", "escalated", "active"]:
            ConversationService.update_conversation_status(conversation, status)
            conversation.refresh_from_db()
            assert conversation.status == status

    def test_update_context(self):
        """Test updating conversation context."""
        conversation = AgentConversationFactory(context={"initial": "value"})

        ConversationService.update_context(conversation, {"new_key": "new_value", "number": 42})

        conversation.refresh_from_db()
        assert conversation.context["initial"] == "value"
        assert conversation.context["new_key"] == "new_value"
        assert conversation.context["number"] == 42

    def test_update_context_overwrites_existing_keys(self):
        """Test that context update overwrites existing keys."""
        conversation = AgentConversationFactory(context={"key": "old_value"})

        ConversationService.update_context(conversation, {"key": "new_value"})

        conversation.refresh_from_db()
        assert conversation.context["key"] == "new_value"

    def test_update_context_empty_update(self):
        """Test updating with empty dict."""
        conversation = AgentConversationFactory(context={"key": "value"})

        ConversationService.update_context(conversation, {})

        conversation.refresh_from_db()
        assert conversation.context == {"key": "value"}

    def test_add_tool_invocation(self):
        """Test recording tool invocation."""
        conversation = AgentConversationFactory(tool_invocations=[])
        tool_input = {"param1": "value1", "param2": 123}
        tool_output = {"result": "success", "data": [1, 2, 3]}

        ConversationService.add_tool_invocation(
            conversation=conversation,
            tool_name="symptom_checker",
            tool_input=tool_input,
            tool_output=tool_output,
        )

        conversation.refresh_from_db()
        assert len(conversation.tool_invocations) == 1
        invocation = conversation.tool_invocations[0]
        assert invocation["tool"] == "symptom_checker"
        assert invocation["input"] == tool_input
        assert invocation["output"] == tool_output
        assert "timestamp" in invocation

    def test_add_tool_invocation_appends(self):
        """Test that tool invocations are appended."""
        conversation = AgentConversationFactory(tool_invocations=[{"tool": "existing"}])

        ConversationService.add_tool_invocation(
            conversation=conversation,
            tool_name="new_tool",
            tool_input={},
            tool_output={},
        )

        conversation.refresh_from_db()
        assert len(conversation.tool_invocations) == 2
        assert conversation.tool_invocations[0]["tool"] == "existing"
        assert conversation.tool_invocations[1]["tool"] == "new_tool"

    def test_add_tool_invocation_multiple(self):
        """Test adding multiple tool invocations."""
        conversation = AgentConversationFactory(tool_invocations=[])

        for i in range(3):
            ConversationService.add_tool_invocation(
                conversation=conversation,
                tool_name=f"tool_{i}",
                tool_input={"index": i},
                tool_output={"result": f"output_{i}"},
            )

        conversation.refresh_from_db()
        assert len(conversation.tool_invocations) == 3


@pytest.mark.django_db
class TestContextService:
    """Tests for ContextService."""

    def test_get_patient_context_basic(self):
        """Test getting basic patient context."""
        patient = PatientFactory(
            surgery_type="Knee Replacement",
            surgery_date=date.today() - timedelta(days=10),
            status="green",
        )

        context = ContextService.get_patient_context(patient)

        assert context["id"] == str(patient.id)
        assert context["name"] == f"{patient.user.first_name} {patient.user.last_name}"
        assert context["surgery_type"] == "Knee Replacement"
        assert context["days_post_op"] == 10
        assert context["status"] == "green"
        assert context["phone"] == str(patient.user.phone_number)

    def test_get_patient_context_no_surgery_date(self):
        """Test patient context when surgery_date is None."""
        patient = PatientFactory(surgery_date=None, surgery_type="")

        context = ContextService.get_patient_context(patient)

        assert context["surgery_date"] is None
        assert context["days_post_op"] is None
        assert context["surgery_type"] == "Unknown"

    def test_get_patient_context_no_phone(self):
        """Test patient context when phone is empty string."""
        patient = PatientFactory()
        patient.user.phone_number = ""
        patient.user.save()

        context = ContextService.get_patient_context(patient)

        assert context["phone"] is None

    def test_get_patient_context_no_dob(self):
        """Test patient context when date_of_birth is None - skip (DB constraint)."""
        pytest.skip("Patient.date_of_birth has NOT NULL constraint in DB")

    def test_get_patient_context_with_active_pathway(self):
        """Test patient context includes active pathway."""
        patient = PatientFactory()
        pathway = ClinicalPathway.objects.create(
            name="Knee Recovery",
            surgery_type="Knee Replacement",
            description="Standard knee recovery",
            duration_days=90,
        )
        patient_pathway = PatientPathway.objects.create(  # noqa: F841
            patient=patient,
            pathway=pathway,
            status="active",
        )

        context = ContextService.get_patient_context(patient)

        assert "pathway" in context
        assert context["pathway"]["name"] == "Knee Recovery"
        assert context["pathway"]["surgery_type"] == "Knee Replacement"
        assert "started_at" in context["pathway"]

    def test_get_patient_context_no_active_pathway(self):
        """Test patient context without active pathway."""
        patient = PatientFactory()
        pathway = ClinicalPathway.objects.create(
            name="Knee Recovery",
            surgery_type="Knee Replacement",
            description="Standard knee recovery",
            duration_days=90,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="completed",
        )

        context = ContextService.get_patient_context(patient)

        assert "pathway" not in context

    def test_get_pathway_context_no_active_pathway(self):
        """Test pathway context when no active pathway."""
        patient = PatientFactory()

        context = ContextService.get_pathway_context(patient)

        assert context["current_phase"] == "unknown"
        assert context["milestones"] == []

    def test_get_pathway_context_with_milestones(self):
        """Test pathway context with current and next milestones."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=5))
        pathway = ClinicalPathway.objects.create(
            name="Knee Recovery",
            surgery_type="Knee Replacement",
            description="Standard knee recovery",
            duration_days=90,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="active",
        )

        # Create milestones
        milestone_1 = PathwayMilestone.objects.create(  # noqa: F841
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3 Check-in",
            expected_symptoms=["pain", "swelling"],
            activities=["rest", "ice"],
            red_flags=["fever"],
        )
        milestone_2 = PathwayMilestone.objects.create(  # noqa: F841
            pathway=pathway,
            day=7,
            phase="early",
            title="Day 7 Check-in",
            expected_symptoms=["less pain"],
            activities=["light walking"],
            red_flags=["infection"],
        )
        PathwayMilestone.objects.create(
            pathway=pathway,
            day=14,
            phase="middle",
            title="Day 14 Check-in",
            expected_symptoms=["stiffness"],
            activities=["exercises"],
            red_flags=["severe pain"],
        )

        context = ContextService.get_pathway_context(patient)

        assert context["current_phase"] == "early"
        assert context["current_milestone"]["day"] == 3
        assert context["current_milestone"]["title"] == "Day 3 Check-in"
        assert context["current_milestone"]["expected_symptoms"] == ["pain", "swelling"]
        assert context["next_milestone"]["day"] == 7
        assert context["next_milestone"]["title"] == "Day 7 Check-in"

    def test_get_pathway_context_no_current_milestone(self):
        """Test pathway context when no milestone matches current day."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=1))
        pathway = ClinicalPathway.objects.create(
            name="Knee Recovery",
            surgery_type="Knee Replacement",
            description="Standard knee recovery",
            duration_days=90,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="active",
        )

        # Only milestone is at day 3
        PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3 Check-in",
            expected_symptoms=["pain"],
            activities=["rest"],
            red_flags=["fever"],
        )

        context = ContextService.get_pathway_context(patient)

        assert context["current_phase"] == "unknown"
        assert context["current_milestone"] is None
        assert context["next_milestone"]["day"] == 3

    def test_get_pathway_context_no_next_milestone(self):
        """Test pathway context when no next milestone."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=30))
        pathway = ClinicalPathway.objects.create(
            name="Knee Recovery",
            surgery_type="Knee Replacement",
            description="Standard knee recovery",
            duration_days=90,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="active",
        )

        # Only milestone is at day 3
        PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3 Check-in",
            expected_symptoms=["pain"],
            activities=["rest"],
            red_flags=["fever"],
        )

        context = ContextService.get_pathway_context(patient)

        assert context["current_milestone"]["day"] == 3
        assert context["next_milestone"] is None

    def test_get_pathway_context_inactive_milestones_excluded(self):
        """Test that inactive milestones are excluded."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=5))
        pathway = ClinicalPathway.objects.create(
            name="Knee Recovery",
            surgery_type="Knee Replacement",
            description="Standard knee recovery",
            duration_days=90,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="active",
        )

        # Active milestone
        PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Active Milestone",
            is_active=True,
        )
        # Inactive milestone
        PathwayMilestone.objects.create(
            pathway=pathway,
            day=7,
            phase="early",
            title="Inactive Milestone",
            is_active=False,
        )

        context = ContextService.get_pathway_context(patient)

        assert context["current_milestone"]["title"] == "Active Milestone"
        assert context["next_milestone"] is None

    def test_get_recent_symptoms_from_messages(self):
        """Test extracting symptoms from recent messages."""
        conversation = AgentConversationFactory()

        AgentMessageFactory(
            conversation=conversation,
            role="user",
            content="I have severe pain in my knee. The pain is constant.",
        )
        AgentMessageFactory(
            conversation=conversation,
            role="user",
            content="Also experiencing some swelling and redness.",
        )
        AgentMessageFactory(
            conversation=conversation,
            role="assistant",
            content="I understand you're having pain.",
        )

        symptoms = ContextService.get_recent_symptoms(conversation)

        assert len(symptoms) > 0
        # Should find pain-related sentences
        assert any("pain" in s.lower() for s in symptoms)

    def test_get_recent_symptoms_only_user_messages(self):
        """Test that only user messages are analyzed."""
        conversation = AgentConversationFactory()

        AgentMessageFactory(
            conversation=conversation,
            role="assistant",
            content="I have pain and fever.",  # Should be ignored
        )
        AgentMessageFactory(
            conversation=conversation,
            role="user",
            content="I feel fine actually.",
        )

        symptoms = ContextService.get_recent_symptoms(conversation)

        # Should not find symptoms from assistant message
        assert len(symptoms) == 0

    def test_get_recent_symptoms_empty_conversation(self):
        """Test getting symptoms from empty conversation."""
        conversation = AgentConversationFactory()

        symptoms = ContextService.get_recent_symptoms(conversation)

        assert symptoms == []

    def test_get_recent_symptoms_no_symptoms_found(self):
        """Test when no symptom keywords are found."""
        conversation = AgentConversationFactory()

        AgentMessageFactory(
            conversation=conversation,
            role="user",
            content="The weather is nice today. I went for a walk.",
        )

        symptoms = ContextService.get_recent_symptoms(conversation)

        assert symptoms == []

    def test_get_recent_symptoms_deduplication(self):
        """Test that symptoms are deduplicated."""
        conversation = AgentConversationFactory()

        AgentMessageFactory(
            conversation=conversation,
            role="user",
            content="I have pain. The pain is severe.",
        )

        symptoms = ContextService.get_recent_symptoms(conversation)

        # Should deduplicate
        assert len(symptoms) <= 1

    def test_get_recent_symptoms_limit_five(self):
        """Test that at most 5 symptoms are returned."""
        conversation = AgentConversationFactory()

        # Create messages with different symptoms
        for i in range(10):
            AgentMessageFactory(
                conversation=conversation,
                role="user",
                content=f"I have pain {i}. I have fever {i}.",
            )

        symptoms = ContextService.get_recent_symptoms(conversation)

        assert len(symptoms) <= 5

    def test_assemble_full_context_without_conversation(self):
        """Test assembling context without conversation."""
        patient = PatientFactory()

        context = ContextService.assemble_full_context(patient)

        assert "patient" in context
        assert "pathway" in context
        assert "conversation_history" not in context
        assert "recent_symptoms" not in context
        assert "state" not in context

    def test_assemble_full_context_with_conversation(self):
        """Test assembling context with conversation."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)
        ConversationStateFactory(conversation=conversation)

        AgentMessageFactory(conversation=conversation, role="user", content="I have pain")

        context = ContextService.assemble_full_context(patient, conversation)

        assert "patient" in context
        assert "pathway" in context
        assert "conversation_history" in context
        assert "recent_symptoms" in context
        assert "state" in context
        assert context["state"]["patient_summary"] == conversation.state.patient_summary

    def test_assemble_full_context_no_state(self):
        """Test assembling context when conversation has no state."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)
        # No state created

        context = ContextService.assemble_full_context(patient, conversation)

        assert "conversation_history" in context
        assert "state" not in context

    def test_assemble_full_context_with_pathway(self):
        """Test assembling context with active pathway."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=5))
        pathway = ClinicalPathway.objects.create(
            name="Knee Recovery",
            surgery_type="Knee Replacement",
            description="Standard knee recovery",
            duration_days=90,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="active",
        )
        PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3 Check-in",
            expected_symptoms=["pain"],
            activities=["rest"],
            red_flags=["fever"],
        )

        context = ContextService.assemble_full_context(patient)

        assert context["pathway"]["current_phase"] == "early"


@pytest.mark.django_db(transaction=True)
class TestEscalationService:
    """Tests for EscalationService."""

    def test_create_escalation_with_conversation(self):
        """Test creating escalation with conversation."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient, status="active")
        patient_context = {"key": "value"}

        escalation = EscalationService.create_escalation(
            patient=patient,
            conversation=conversation,
            reason="Severe pain reported",
            severity="urgent",
            conversation_summary="Patient reported severe pain",
            patient_context=patient_context,
        )

        assert escalation.patient == patient
        assert escalation.conversation == conversation
        assert escalation.reason == "Severe pain reported"
        assert escalation.severity == "urgent"
        assert escalation.conversation_summary == "Patient reported severe pain"
        assert escalation.patient_context == patient_context
        assert escalation.status == "pending"

        # Verify conversation was updated
        conversation.refresh_from_db()
        assert conversation.status == "escalated"
        assert conversation.escalation_reason == "Severe pain reported"

    def test_create_escalation_without_conversation(self):
        """Test creating escalation without conversation."""
        patient = PatientFactory()

        escalation = EscalationService.create_escalation(
            patient=patient,
            conversation=None,
            reason="Direct escalation",
            severity="critical",
        )

        assert escalation.patient == patient
        assert escalation.conversation is None
        assert escalation.reason == "Direct escalation"
        assert escalation.severity == "critical"

    def test_create_escalation_default_patient_context(self):
        """Test that None patient_context defaults to empty dict."""
        patient = PatientFactory()

        escalation = EscalationService.create_escalation(
            patient=patient,
            conversation=None,
            reason="Test",
            severity="routine",
            patient_context=None,
        )

        assert escalation.patient_context == {}

    def test_create_escalation_all_severities(self):
        """Test creating escalations with all severity levels."""
        patient = PatientFactory()

        for severity in ["critical", "urgent", "routine"]:
            escalation = EscalationService.create_escalation(
                patient=patient,
                conversation=None,
                reason=f"Test {severity}",
                severity=severity,
            )
            assert escalation.severity == severity

    def test_acknowledge_escalation_success(self):
        """Test successful escalation acknowledgment."""
        patient = PatientFactory()
        escalation = EscalationFactory(patient=patient, status="pending")
        clinician = UserFactory()

        result = EscalationService.acknowledge_escalation(
            escalation_id=str(escalation.id),
            clinician_id=clinician.id,
        )

        assert result is True
        escalation.refresh_from_db()
        assert escalation.status == "acknowledged"
        assert escalation.assigned_to == clinician
        assert escalation.acknowledged_at is not None

    def test_acknowledge_escalation_not_found(self):
        """Test acknowledging non-existent escalation."""
        clinician = UserFactory()

        result = EscalationService.acknowledge_escalation(
            escalation_id=str(uuid.uuid4()),
            clinician_id=clinician.id,
        )

        assert result is False

    def test_acknowledge_escalation_clinician_not_found(self):
        """Test acknowledging with non-existent clinician."""
        patient = PatientFactory()
        escalation = EscalationFactory(patient=patient, status="pending")

        result = EscalationService.acknowledge_escalation(
            escalation_id=str(escalation.id),
            clinician_id=99999,
        )

        assert result is False

    def test_resolve_escalation_success(self):
        """Test successful escalation resolution."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient, status="escalated")
        escalation = EscalationFactory(
            patient=patient,
            conversation=conversation,
            status="acknowledged",
        )

        result = EscalationService.resolve_escalation(
            escalation_id=str(escalation.id),
            resolution_notes="Patient feeling better",
        )

        assert result is True
        escalation.refresh_from_db()
        assert escalation.status == "resolved"
        assert escalation.resolved_at is not None

        # Verify conversation was updated
        conversation.refresh_from_db()
        assert conversation.status == "completed"

    def test_resolve_escalation_without_conversation(self):
        """Test resolving escalation without conversation."""
        patient = PatientFactory()
        escalation = EscalationFactory(patient=patient, conversation=None, status="pending")

        result = EscalationService.resolve_escalation(
            escalation_id=str(escalation.id),
            resolution_notes="Resolved",
        )

        assert result is True
        escalation.refresh_from_db()
        assert escalation.status == "resolved"

    def test_resolve_escalation_not_found(self):
        """Test resolving non-existent escalation."""
        result = EscalationService.resolve_escalation(
            escalation_id=str(uuid.uuid4()),
            resolution_notes="Notes",
        )

        assert result is False

    def test_get_pending_escalations(self):
        """Test getting pending escalations."""
        patient1 = PatientFactory()
        patient2 = PatientFactory()
        hospital = HospitalFactory()
        patient3 = PatientFactory(hospital=hospital)

        # Create escalations with different statuses
        EscalationFactory(patient=patient1, status="pending")
        EscalationFactory(patient=patient2, status="pending")
        EscalationFactory(patient=patient3, status="acknowledged")
        EscalationFactory(patient=patient1, status="resolved")

        pending = EscalationService.get_pending_escalations()

        assert pending.count() == 2
        assert all(e.status == "pending" for e in pending)

    def test_get_pending_escalations_with_hospital_filter(self):
        """Test getting pending escalations filtered by hospital."""
        hospital1 = HospitalFactory()
        hospital2 = HospitalFactory()
        patient1 = PatientFactory(hospital=hospital1)
        patient2 = PatientFactory(hospital=hospital2)
        patient3 = PatientFactory(hospital=None)

        EscalationFactory(patient=patient1, status="pending")
        EscalationFactory(patient=patient2, status="pending")
        EscalationFactory(patient=patient3, status="pending")

        pending = EscalationService.get_pending_escalations(hospital_id=hospital1.id)

        assert pending.count() == 1
        assert pending.first().patient == patient1

    def test_get_pending_escalations_no_pending(self):
        """Test when no pending escalations exist."""
        patient = PatientFactory()
        EscalationFactory(patient=patient, status="resolved")

        pending = EscalationService.get_pending_escalations()

        assert pending.count() == 0

    def test_get_pending_escalations_ordered(self):
        """Test that pending escalations are ordered by created_at desc."""
        patient = PatientFactory()

        esc1 = EscalationFactory(patient=patient, status="pending")  # noqa: F841
        esc2 = EscalationFactory(patient=patient, status="pending")  # noqa: F841
        esc3 = EscalationFactory(patient=patient, status="pending")  # noqa: F841

        pending = list(EscalationService.get_pending_escalations())

        # Should be newest first
        assert pending[0].created_at >= pending[1].created_at

    def test_generate_conversation_summary_with_messages(self):
        """Test generating summary with messages."""
        conversation = AgentConversationFactory()

        AgentMessageFactory(conversation=conversation, role="user", content="Hello, I have a question")
        AgentMessageFactory(conversation=conversation, role="assistant", content="How can I help?")
        AgentMessageFactory(
            conversation=conversation,
            role="user",
            content=(
                "This is a very long message that should be truncated "
                "in the summary because it exceeds one hundred characters easily"
            ),
        )

        summary = EscalationService.generate_conversation_summary(conversation)

        assert "Patient:" in summary
        assert "AI:" in summary
        assert "..." in summary  # Truncated message

    def test_generate_conversation_summary_empty(self):
        """Test generating summary for conversation with no messages."""
        conversation = AgentConversationFactory()

        summary = EscalationService.generate_conversation_summary(conversation)

        assert summary == "No messages in conversation."

    def test_generate_conversation_summary_single_message(self):
        """Test generating summary with single message."""
        conversation = AgentConversationFactory()
        AgentMessageFactory(conversation=conversation, role="user", content="Hello")

        summary = EscalationService.generate_conversation_summary(conversation)

        assert "Patient: Hello" in summary

    def test_generate_handoff_notes(self):
        """Test generating handoff notes."""
        patient = PatientFactory(
            surgery_type="Knee Replacement",
            surgery_date=date.today() - timedelta(days=5),
        )
        conversation = AgentConversationFactory(
            patient=patient,
            agent_type="supervisor",
            tool_invocations=[{"tool": "symptom_checker"}],
        )

        AgentMessageFactory(
            conversation=conversation,
            role="assistant",
            agent_type="care_coordinator",
            content="I can help with your recovery",
            confidence_score=0.9,
        )

        EscalationFactory(conversation=conversation, reason="Previous issue", status="resolved")

        notes = EscalationService.generate_handoff_notes(conversation, "Severe pain reported")

        assert "AI Handoff Notes" in notes
        assert patient.user.first_name in notes
        assert "Severe pain reported" in notes
        assert "Knee Replacement" in notes
        assert "care_coordinator" in notes
        assert "symptom_checker" in notes or "1 invocations" in notes

    def test_generate_handoff_notes_no_ai_messages(self):
        """Test handoff notes when no AI messages exist."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)

        AgentMessageFactory(conversation=conversation, role="user", content="Hello")

        notes = EscalationService.generate_handoff_notes(conversation, "Test reason")

        assert "No AI responses recorded" in notes

    def test_generate_handoff_notes_no_escalations(self):
        """Test handoff notes when no previous escalations."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)

        notes = EscalationService.generate_handoff_notes(conversation, "Test reason")

        assert "No previous escalations" in notes

    def test_generate_handoff_notes_no_phone(self):
        """Test handoff notes when patient has no phone."""
        patient = PatientFactory()
        patient.user.phone_number = ""
        patient.user.save()
        conversation = AgentConversationFactory(patient=patient)

        notes = EscalationService.generate_handoff_notes(conversation, "Test")

        assert "N/A" in notes or "Phone:" in notes

    def test_generate_structured_handoff(self):
        """Test generating structured handoff data."""
        patient = PatientFactory(
            surgery_type="Knee Replacement",
            surgery_date=date.today() - timedelta(days=5),
            status="yellow",
        )
        conversation = AgentConversationFactory(
            patient=patient,
            agent_type="supervisor",
        )

        AgentMessageFactory(
            conversation=conversation,
            role="user",
            content="I have severe pain",
        )
        AgentMessageFactory(
            conversation=conversation,
            role="assistant",
            agent_type="care_coordinator",
            content="Let me help",
            confidence_score=0.85,
            escalation_triggered=True,
        )

        handoff = EscalationService.generate_structured_handoff(conversation, "Critical symptom")

        assert handoff["patient"]["id"] == str(patient.id)
        assert handoff["patient"]["name"] == f"{patient.user.first_name} {patient.user.last_name}"
        assert handoff["patient"]["surgery_type"] == "Knee Replacement"
        assert handoff["patient"]["days_post_op"] == 5
        assert handoff["patient"]["status"] == "yellow"

        assert handoff["escalation"]["reason"] == "Critical symptom"
        assert handoff["escalation"]["severity"] == "critical"

        assert handoff["conversation"]["id"] == str(conversation.id)
        assert handoff["conversation"]["agent_type"] == "supervisor"
        assert handoff["conversation"]["message_count"] == 2

        assert len(handoff["timeline"]) == 2
        assert handoff["timeline"][0]["role"] == "user"
        assert handoff["timeline"][1]["confidence"] == 0.85

        assert "context" in handoff
        assert "ai_coverage" in handoff

    def test_generate_structured_handoff_critical_severity(self):
        """Test that 'critical' in reason sets severity to critical."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)

        handoff = EscalationService.generate_structured_handoff(conversation, "This is CRITICAL")

        assert handoff["escalation"]["severity"] == "critical"

    def test_generate_structured_handoff_urgent_severity(self):
        """Test that reason without 'critical' sets severity to urgent."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)

        handoff = EscalationService.generate_structured_handoff(conversation, "Patient needs help")

        assert handoff["escalation"]["severity"] == "urgent"

    def test_generate_structured_handoff_empty_conversation(self):
        """Test structured handoff with no messages."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)

        handoff = EscalationService.generate_structured_handoff(conversation, "Test")

        assert handoff["conversation"]["message_count"] == 0
        assert handoff["timeline"] == []

    def test_generate_structured_handoff_message_truncation(self):
        """Test that long messages are truncated."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)

        long_content = "A" * 300
        AgentMessageFactory(conversation=conversation, role="user", content=long_content)

        handoff = EscalationService.generate_structured_handoff(conversation, "Test")

        assert len(handoff["timeline"][0]["content"]) < 250
        assert "..." in handoff["timeline"][0]["content"]


@pytest.mark.django_db
class TestServiceIntegration:
    """Integration tests combining multiple services."""

    def test_full_conversation_flow(self):
        """Test a complete conversation flow with escalation."""
        patient = PatientFactory()

        # Create conversation
        conversation = ConversationService.get_or_create_conversation(patient)

        # Add messages
        ConversationService.add_message(
            conversation=conversation,
            role="user",
            content="I have severe pain and fever",
        )
        ConversationService.add_message(
            conversation=conversation,
            role="assistant",
            content="I understand. Let me check your symptoms.",
            agent_type="nurse_triage",
            confidence_score=0.8,
        )

        # Update context
        ConversationService.update_context(conversation, {"symptoms": ["pain", "fever"]})

        # Add tool invocation
        ConversationService.add_tool_invocation(
            conversation=conversation,
            tool_name="symptom_checker",
            tool_input={"symptoms": ["pain", "fever"]},
            tool_output={"severity": "high"},
        )

        # Get history
        history = ConversationService.get_conversation_history(conversation)
        assert len(history) == 2

        # Get context
        context = ContextService.assemble_full_context(patient, conversation)
        assert "patient" in context
        assert "conversation_history" in context

        # Create escalation
        escalation = EscalationService.create_escalation(
            patient=patient,
            conversation=conversation,
            reason="High severity symptoms",
            severity="urgent",
            conversation_summary="Patient reported pain and fever",
        )

        # Verify conversation status updated
        conversation.refresh_from_db()
        assert conversation.status == "escalated"

        # Generate handoff notes
        notes = EscalationService.generate_handoff_notes(conversation, "High severity symptoms")
        assert "AI Handoff Notes" in notes

        # Acknowledge escalation
        clinician = UserFactory()
        result = EscalationService.acknowledge_escalation(
            escalation_id=str(escalation.id),
            clinician_id=clinician.id,
        )
        assert result is True

        # Resolve escalation
        result = EscalationService.resolve_escalation(
            escalation_id=str(escalation.id),
            resolution_notes="Patient contacted and advised",
        )
        assert result is True

        # Verify final state
        escalation.refresh_from_db()
        assert escalation.status == "resolved"
        conversation.refresh_from_db()
        assert conversation.status == "completed"

    def test_concurrent_conversations_same_patient(self):
        """Test that patient can have multiple conversations."""
        patient = PatientFactory()

        conv1 = ConversationService.get_or_create_conversation(patient, agent_type="supervisor")
        conv1.status = "completed"
        conv1.save()

        conv2 = ConversationService.get_or_create_conversation(patient, agent_type="nurse_triage")

        assert conv1.id != conv2.id
        assert conv1.agent_type == "supervisor"
        assert conv2.agent_type == "nurse_triage"

    def test_escalation_workflow_with_pathway(self):
        """Test escalation with patient on a pathway."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=5))

        # Create pathway
        pathway = ClinicalPathway.objects.create(
            name="Knee Recovery",
            surgery_type="Knee Replacement",
            description="Standard recovery",
            duration_days=90,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="active",
        )
        PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3",
            expected_symptoms=["pain", "swelling"],
            activities=["rest"],
            red_flags=["fever"],
        )

        # Create conversation and escalate
        conversation = AgentConversationFactory(patient=patient)
        escalation = EscalationService.create_escalation(  # noqa: F841
            patient=patient,
            conversation=conversation,
            reason="Fever detected",
            severity="urgent",
        )

        # Generate structured handoff
        handoff = EscalationService.generate_structured_handoff(conversation, "Fever detected")

        assert handoff["patient"]["surgery_type"] == "Knee Replacement"
        assert "id" in handoff["patient"]
        assert "name" in handoff["patient"]

    def test_multiple_escalations_same_conversation(self):
        """Test multiple escalations for same conversation."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)

        esc1 = EscalationService.create_escalation(
            patient=patient,
            conversation=conversation,
            reason="First issue",
            severity="routine",
        )
        esc1.status = "resolved"
        esc1.save()

        esc2 = EscalationService.create_escalation(  # noqa: F841
            patient=patient,
            conversation=conversation,
            reason="Second issue",
            severity="urgent",
        )

        # Generate handoff - should show escalation history
        notes = EscalationService.generate_handoff_notes(conversation, "Third issue")

        assert conversation.escalations.count() == 2
        assert "First issue" in notes or "Recent Escalation History" in notes
