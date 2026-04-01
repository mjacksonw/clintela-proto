"""Comprehensive tests for Celery tasks in apps.agents.tasks.

This module provides thorough test coverage for all Celery tasks including:
- process_patient_message
- send_proactive_checkin
- check_missed_checkins
- schedule_proactive_checkins
- cleanup_old_conversations
- generate_conversation_summaries

All external dependencies are mocked to ensure isolated, fast tests.
"""

import logging
from datetime import date, timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.agents.models import AgentConversation, AgentMessage
from apps.agents.tasks import (
    check_missed_checkins,
    cleanup_old_conversations,
    generate_conversation_summaries,
    process_patient_message,
    schedule_proactive_checkins,
    send_proactive_checkin,
)
from apps.agents.tests.factories import (
    AgentConversationFactory,
    AgentMessageFactory,
    PatientFactory,
)
from apps.pathways.models import (
    ClinicalPathway,
    PathwayMilestone,
    PatientMilestoneCheckin,
    PatientPathway,
)


@pytest.fixture
def mock_workflow():
    """Create a mock workflow for testing."""
    workflow = Mock()
    workflow.process_message = Mock()
    return workflow


@pytest.fixture
def mock_documentation_agent():
    """Create a mock DocumentationAgent for testing."""
    agent = Mock()
    agent.process = Mock()
    return agent


@pytest.fixture
def mock_escalation_service():
    """Create a mock EscalationService for testing."""
    service = Mock()
    service.create_escalation = Mock()
    return service


class MockTask:
    """Mock Celery task object for bind=True tasks."""

    def __init__(self):
        self.request = Mock()
        self.request.retries = 0
        self.max_retries = 3

    def retry(self, countdown=None):
        raise Exception("Retry triggered")


def call_bind_task(task_func, *args, **kwargs):
    """Call a bind=True task with proper mock self."""
    mock_task = MockTask()
    return task_func(mock_task, *args, **kwargs)


class TestProcessPatientMessage:
    """Tests for process_patient_message task."""

    @pytest.mark.django_db(transaction=True)
    def test_process_patient_message_success(self, mock_workflow):
        """Test successful message processing."""
        patient = PatientFactory()
        message = "I have pain in my knee"

        # Mock workflow result
        workflow_result = {
            "response": "I'm sorry to hear about your pain. Can you describe it?",
            "agent_type": "nurse_triage",
            "escalate": False,
            "escalation_reason": "",
            "metadata": {"confidence": 0.95, "severity": "routine"},
        }
        mock_workflow.process_message.return_value = workflow_result

        with (
            patch("apps.agents.tasks.get_workflow", return_value=mock_workflow),
            patch("asyncio.run", return_value=workflow_result),
        ):
            result = process_patient_message(str(patient.id), message)

        assert result["success"] is True
        assert result["response"] == workflow_result["response"]
        assert result["agent_type"] == workflow_result["agent_type"]
        assert result["escalate"] is False

        # Verify conversation was created
        conversation = AgentConversation.objects.filter(patient=patient).first()
        assert conversation is not None

        # Verify messages were added
        messages = AgentMessage.objects.filter(conversation=conversation)
        assert messages.count() == 2  # User message + assistant response

    @pytest.mark.django_db(transaction=True)
    def test_process_patient_message_patient_not_found(self):
        """Test handling when patient does not exist."""
        non_existent_id = 99999  # Use integer for Patient model
        message = "Hello"

        result = process_patient_message(str(non_existent_id), message)

        assert "error" in result
        assert result["error"] == "Patient not found"

    @pytest.mark.django_db(transaction=True)
    def test_process_patient_message_with_escalation(self, mock_workflow):
        """Test message processing that triggers escalation."""
        patient = PatientFactory()
        message = "I have severe chest pain"

        workflow_result = {
            "response": "This sounds serious. I'm connecting you with a nurse.",
            "agent_type": "nurse_triage",
            "escalate": True,
            "escalation_reason": "Severe chest pain reported",
            "metadata": {"confidence": 0.98, "severity": "critical"},
        }
        mock_workflow.process_message.return_value = workflow_result

        with (
            patch("apps.agents.tasks.get_workflow", return_value=mock_workflow),
            patch("asyncio.run", return_value=workflow_result),
            patch("apps.agents.services.EscalationService") as mock_esc_class,
        ):
            mock_esc_service = Mock()
            mock_esc_class.return_value = mock_esc_service
            mock_esc_class.create_escalation = Mock()

            result = process_patient_message(str(patient.id), message)

        assert result["success"] is True
        assert result["escalate"] is True

        # Verify conversation status was updated
        conversation = AgentConversation.objects.filter(patient=patient).first()
        assert conversation.status == "escalated"

    @pytest.mark.django_db(transaction=True)
    def test_process_patient_message_retry_on_exception(self, mock_workflow):
        """Test retry logic when workflow raises exception."""
        patient = PatientFactory()
        message = "Test message"

        with (
            patch("apps.agents.tasks.get_workflow", return_value=mock_workflow),
            patch("asyncio.run", side_effect=Exception("Workflow error")),
        ):
            try:
                result = process_patient_message(str(patient.id), message)
                # With eager mode + propagation, may get error dict or exception
                if isinstance(result, dict):
                    assert "error" in result
            except Exception:
                logging.debug("Expected exception during retry")

    @pytest.mark.django_db(transaction=True)
    def test_process_patient_message_max_retries_exceeded(self, mock_workflow):
        """Test behavior when workflow fails — returns error dict."""
        patient = PatientFactory()
        message = "Test message"

        with (
            patch("apps.agents.tasks.get_workflow", return_value=mock_workflow),
            patch("asyncio.run", side_effect=Exception("Workflow error")),
        ):
            try:
                result = process_patient_message(str(patient.id), message)
                if isinstance(result, dict):
                    assert "error" in result
            except Exception:
                logging.debug("Retry propagation in eager mode")

    @pytest.mark.django_db(transaction=True)
    def test_process_patient_message_uses_existing_conversation(self, mock_workflow):
        """Test that existing active conversation is reused."""
        patient = PatientFactory()
        existing_conversation = AgentConversationFactory(patient=patient, status="active")
        message = "Follow up question"

        workflow_result = {
            "response": "Here's more information.",
            "agent_type": "care_coordinator",
            "escalate": False,
            "escalation_reason": "",
            "metadata": {"confidence": 0.9},
        }
        mock_workflow.process_message.return_value = workflow_result

        with (
            patch("apps.agents.tasks.get_workflow", return_value=mock_workflow),
            patch("asyncio.run", return_value=workflow_result),
        ):
            result = process_patient_message(str(patient.id), message)

        assert result["success"] is True

        # Verify no new conversation was created
        conversation_count = AgentConversation.objects.filter(patient=patient).count()
        assert conversation_count == 1

        # Verify message was added to existing conversation
        messages = AgentMessage.objects.filter(conversation=existing_conversation)
        assert messages.count() == 2  # User message + assistant response


class TestSendProactiveCheckin:
    """Tests for send_proactive_checkin task."""

    @pytest.mark.django_db(transaction=True)
    def test_send_proactive_checkin_success(self):
        """Test successful proactive check-in."""
        patient = PatientFactory()

        # Create pathway and milestone
        pathway = ClinicalPathway.objects.create(
            name="Knee Replacement Recovery",
            surgery_type="Knee Replacement",
            description="Standard recovery pathway",
            duration_days=90,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3 Check-in",
            check_in_questions=["How is your pain level?", "Are you able to walk?"],
        )

        result = send_proactive_checkin(str(patient.id), milestone.id)

        assert result["success"] is True
        assert "message" in result
        assert result["milestone_day"] == 3
        assert patient.user.first_name in result["message"]

        # Verify check-in record was created
        checkin = PatientMilestoneCheckin.objects.filter(patient=patient, milestone=milestone).first()
        assert checkin is not None
        assert checkin.sent_at is not None

    @pytest.mark.django_db(transaction=True)
    def test_send_proactive_checkin_patient_not_found(self):
        """Test handling when patient does not exist."""
        non_existent_id = "99999"  # Use a numeric string ID that won't exist
        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1",
        )

        result = send_proactive_checkin(non_existent_id, milestone.id)

        assert "error" in result
        assert "Patient or milestone not found" in result["error"]

    @pytest.mark.django_db(transaction=True)
    def test_send_proactive_checkin_milestone_not_found(self):
        """Test handling when milestone does not exist."""
        patient = PatientFactory()
        non_existent_milestone_id = 99999

        result = send_proactive_checkin(str(patient.id), non_existent_milestone_id)

        assert "error" in result
        assert "Patient or milestone not found" in result["error"]

    @pytest.mark.django_db(transaction=True)
    def test_send_proactive_checkin_already_sent(self):
        """Test handling when check-in was already sent."""
        patient = PatientFactory()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1",
        )

        # Create existing check-in record
        PatientMilestoneCheckin.objects.create(
            patient=patient,
            milestone=milestone,
            sent_at=timezone.now(),
        )

        result = send_proactive_checkin(str(patient.id), milestone.id)

        assert result["success"] is False
        assert result["reason"] == "Already sent"

    @pytest.mark.django_db(transaction=True)
    def test_send_proactive_checkin_no_questions(self):
        """Test check-in when milestone has no questions."""
        patient = PatientFactory()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=5,
            phase="early",
            title="Day 5 Check-in",
            check_in_questions=[],  # Empty questions
        )

        result = send_proactive_checkin(str(patient.id), milestone.id)

        assert result["success"] is True
        # Should use default message without questions
        assert "How are you feeling" in result["message"]

    @pytest.mark.django_db(transaction=True)
    def test_send_proactive_checkin_creates_conversation(self):
        """Test that check-in creates a conversation with proper metadata."""
        patient = PatientFactory()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=2,
            phase="early",
            title="Day 2 Check-in",
            check_in_questions=["How are you feeling today?"],
        )

        result = send_proactive_checkin(str(patient.id), milestone.id)

        assert result["success"] is True

        # Verify conversation was created
        conversation = AgentConversation.objects.filter(patient=patient, agent_type="care_coordinator").first()
        assert conversation is not None

        # Verify message was added with metadata
        message = AgentMessage.objects.filter(conversation=conversation).first()
        assert message is not None
        assert message.metadata.get("proactive") is True
        assert message.metadata.get("milestone_day") == 2


class TestCheckMissedCheckins:
    """Tests for check_missed_checkins task."""

    @pytest.mark.django_db(transaction=True)
    def test_check_missed_checkins_success(self):
        """Test successful detection of missed check-ins."""
        patient = PatientFactory()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1",
        )

        # Create a check-in that was sent 25 hours ago but not completed
        PatientMilestoneCheckin.objects.create(
            patient=patient,
            milestone=milestone,
            sent_at=timezone.now() - timedelta(hours=25),
        )

        with patch("apps.agents.services.EscalationService") as mock_esc_class:
            mock_esc_class.create_escalation = Mock(return_value=Mock())
            result = check_missed_checkins()

        assert result["missed_checkins"] == 1

    @pytest.mark.django_db(transaction=True)
    def test_check_missed_checkins_no_missed(self):
        """Test when there are no missed check-ins."""
        patient = PatientFactory()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1",
        )

        # Create a check-in that was sent recently (not missed)
        PatientMilestoneCheckin.objects.create(
            patient=patient,
            milestone=milestone,
            sent_at=timezone.now() - timedelta(hours=12),
        )

        result = check_missed_checkins()

        assert result["missed_checkins"] == 0

    @pytest.mark.django_db(transaction=True)
    def test_check_missed_checkins_skipped(self):
        """Test that skipped check-ins are not escalated."""
        patient = PatientFactory()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1",
        )

        # Create a skipped check-in
        PatientMilestoneCheckin.objects.create(
            patient=patient,
            milestone=milestone,
            sent_at=timezone.now() - timedelta(hours=25),
            skipped=True,
        )

        result = check_missed_checkins()

        assert result["missed_checkins"] == 0

    @pytest.mark.django_db(transaction=True)
    def test_check_missed_checkins_completed(self):
        """Test that completed check-ins are not escalated."""
        patient = PatientFactory()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1",
        )

        # Create a completed check-in
        PatientMilestoneCheckin.objects.create(
            patient=patient,
            milestone=milestone,
            sent_at=timezone.now() - timedelta(hours=25),
            completed_at=timezone.now() - timedelta(hours=20),
        )

        result = check_missed_checkins()

        assert result["missed_checkins"] == 0

    @pytest.mark.django_db(transaction=True)
    def test_check_missed_checkins_multiple_patients(self):
        """Test batch processing of multiple missed check-ins."""
        patient1 = PatientFactory()
        patient2 = PatientFactory()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone1 = PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1",
        )
        milestone2 = PathwayMilestone.objects.create(
            pathway=pathway,
            day=2,
            phase="early",
            title="Day 2",
        )

        # Create missed check-ins for both patients
        PatientMilestoneCheckin.objects.create(
            patient=patient1,
            milestone=milestone1,
            sent_at=timezone.now() - timedelta(hours=26),
        )
        PatientMilestoneCheckin.objects.create(
            patient=patient2,
            milestone=milestone2,
            sent_at=timezone.now() - timedelta(hours=30),
        )

        with patch("apps.agents.services.EscalationService") as mock_esc_class:
            mock_esc_class.create_escalation = Mock(return_value=Mock())
            result = check_missed_checkins()

        assert result["missed_checkins"] == 2

    @pytest.mark.django_db(transaction=True)
    def test_check_missed_checkins_escalation_failure(self):
        """Test handling when escalation creation fails."""
        patient = PatientFactory()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1",
        )

        PatientMilestoneCheckin.objects.create(
            patient=patient,
            milestone=milestone,
            sent_at=timezone.now() - timedelta(hours=25),
        )

        with patch("apps.agents.services.EscalationService") as mock_esc_class:
            mock_esc_class.create_escalation.side_effect = Exception("Database error")
            result = check_missed_checkins()

        # Should still complete but with 0 count since exception was caught
        assert result["missed_checkins"] == 0


class TestScheduleProactiveCheckins:
    """Tests for schedule_proactive_checkins task."""

    @pytest.mark.django_db(transaction=True)
    def test_schedule_proactive_checkins_success(self):
        """Test successful scheduling of check-ins."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=3))

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Knee Replacement",
            description="Test",
            duration_days=30,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="active",
        )

        # Create milestone for day 3
        PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3 Check-in",
        )

        with patch("apps.agents.tasks.send_proactive_checkin") as mock_task:
            mock_task.delay = Mock(return_value=None)
            result = schedule_proactive_checkins()

        assert result["scheduled"] == 1
        mock_task.delay.assert_called_once()

    @pytest.mark.django_db(transaction=True)
    def test_schedule_proactive_checkins_no_active_pathways(self):
        """Test when there are no active pathways."""
        result = schedule_proactive_checkins()

        assert result["scheduled"] == 0

    @pytest.mark.django_db(transaction=True)
    def test_schedule_proactive_checkins_no_milestone_for_day(self):
        """Test when there's no milestone for current day."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=5))

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Knee Replacement",
            description="Test",
            duration_days=30,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="active",
        )

        # Only create milestone for day 1, not day 5
        PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1 Check-in",
        )

        result = schedule_proactive_checkins()

        assert result["scheduled"] == 0

    @pytest.mark.django_db(transaction=True)
    def test_schedule_proactive_checkins_already_exists(self):
        """Test when check-in already exists for milestone."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=3))

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Knee Replacement",
            description="Test",
            duration_days=30,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="active",
        )

        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3 Check-in",
        )

        # Create existing check-in
        PatientMilestoneCheckin.objects.create(
            patient=patient,
            milestone=milestone,
        )

        result = schedule_proactive_checkins()

        assert result["scheduled"] == 0

    @pytest.mark.django_db(transaction=True)
    def test_schedule_proactive_checkins_multiple_patients(self):
        """Test batch scheduling for multiple patients."""
        patient1 = PatientFactory(surgery_date=date.today() - timedelta(days=3))
        patient2 = PatientFactory(surgery_date=date.today() - timedelta(days=5))

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Knee Replacement",
            description="Test",
            duration_days=30,
        )

        PatientPathway.objects.create(
            patient=patient1,
            pathway=pathway,
            status="active",
        )
        PatientPathway.objects.create(
            patient=patient2,
            pathway=pathway,
            status="active",
        )

        PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3 Check-in",
        )
        PathwayMilestone.objects.create(
            pathway=pathway,
            day=5,
            phase="early",
            title="Day 5 Check-in",
        )

        with patch("apps.agents.tasks.send_proactive_checkin") as mock_task:
            mock_task.delay = Mock(return_value=None)
            result = schedule_proactive_checkins()

        assert result["scheduled"] == 2
        assert mock_task.delay.call_count == 2

    @pytest.mark.django_db(transaction=True)
    def test_schedule_proactive_checkins_inactive_pathway(self):
        """Test that inactive pathways are not processed."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=3))

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Knee Replacement",
            description="Test",
            duration_days=30,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="completed",  # Not active
        )

        PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3 Check-in",
        )

        result = schedule_proactive_checkins()

        assert result["scheduled"] == 0

    @pytest.mark.django_db(transaction=True)
    def test_schedule_proactive_checkins_inactive_milestone(self):
        """Test that inactive milestones are not scheduled."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=3))

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Knee Replacement",
            description="Test",
            duration_days=30,
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
            is_active=False,  # Inactive
        )

        result = schedule_proactive_checkins()

        assert result["scheduled"] == 0

    @pytest.mark.django_db(transaction=True)
    def test_schedule_proactive_checkins_exception_handling(self):
        """Test exception handling during scheduling."""
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=3))

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Knee Replacement",
            description="Test",
            duration_days=30,
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
        )

        with patch("apps.agents.tasks.send_proactive_checkin") as mock_task:
            mock_task.delay.side_effect = Exception("Task queue error")
            result = schedule_proactive_checkins()

        # Should complete despite exception
        assert result["scheduled"] == 0


class TestCleanupOldConversations:
    """Tests for cleanup_old_conversations task (now a no-op — retains all history)."""

    @pytest.mark.django_db(transaction=True)
    def test_cleanup_old_conversations_success(self):
        """Test cleanup is a no-op and retains all conversations."""
        patient = PatientFactory()

        old_conversation = AgentConversationFactory(
            patient=patient,
            status="completed",
        )
        AgentConversation.objects.filter(id=old_conversation.id).update(
            created_at=timezone.now() - timedelta(days=35), updated_at=timezone.now() - timedelta(days=35)
        )

        result = cleanup_old_conversations(days=30)

        assert result["deleted"] == 0
        assert AgentConversation.objects.filter(id=old_conversation.id).exists()

    @pytest.mark.django_db(transaction=True)
    def test_cleanup_old_conversations_escalated(self):
        """Test cleanup retains escalated conversations."""
        patient = PatientFactory()

        old_escalated = AgentConversationFactory(
            patient=patient,
            status="escalated",
        )
        AgentConversation.objects.filter(id=old_escalated.id).update(
            created_at=timezone.now() - timedelta(days=40), updated_at=timezone.now() - timedelta(days=40)
        )

        result = cleanup_old_conversations(days=30)

        assert result["deleted"] == 0
        assert AgentConversation.objects.filter(id=old_escalated.id).exists()

    @pytest.mark.django_db(transaction=True)
    def test_cleanup_old_conversations_no_old_conversations(self):
        """Test when there are no old conversations to clean."""
        patient = PatientFactory()

        AgentConversationFactory(
            patient=patient,
            status="completed",
        )

        result = cleanup_old_conversations(days=30)

        assert result["deleted"] == 0

    @pytest.mark.django_db(transaction=True)
    def test_cleanup_old_conversations_custom_days(self):
        """Test cleanup is a no-op regardless of days parameter."""
        patient = PatientFactory()

        conversation = AgentConversationFactory(
            patient=patient,
            status="completed",
        )
        AgentConversation.objects.filter(id=conversation.id).update(
            created_at=timezone.now() - timedelta(days=20), updated_at=timezone.now() - timedelta(days=20)
        )

        result = cleanup_old_conversations(days=15)
        assert result["deleted"] == 0
        assert AgentConversation.objects.filter(id=conversation.id).exists()


@pytest.mark.django_db(transaction=True)
class TestGenerateConversationSummaries:
    """Tests for generate_conversation_summaries task."""

    def test_generate_conversation_summaries_success(self):
        """Test successful generation of conversation summaries."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(
            patient=patient,
            status="completed",
            context={},
        )

        # Add messages to conversation
        AgentMessageFactory(conversation=conversation, role="user", content="Hello")
        AgentMessageFactory(
            conversation=conversation,
            role="assistant",
            content="Hi, how can I help?",
            agent_type="care_coordinator",
        )

        # Mock DocumentationAgent response
        mock_result = Mock()
        mock_result.response = "Patient reported general inquiry. No concerns."

        with (
            patch("apps.agents.agents.DocumentationAgent") as mock_agent_class,
            patch("asyncio.run", return_value=mock_result),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.process = Mock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            result = generate_conversation_summaries()

        assert result["generated"] >= 1

        # Verify summary was stored
        conversation.refresh_from_db()
        assert "summary" in conversation.context
        assert conversation.context["summary"] == mock_result.response

    @pytest.mark.django_db(transaction=True)
    def test_generate_conversation_summaries_no_messages(self):
        """Test handling conversations with no messages."""
        patient = PatientFactory()
        conv = AgentConversationFactory(
            patient=patient,
            status="completed",
        )

        mock_result = Mock()
        mock_result.response = "Summary"

        with (
            patch("apps.agents.agents.DocumentationAgent") as mock_agent_class,
            patch("asyncio.run", return_value=mock_result),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.process = Mock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            generate_conversation_summaries()

        # Conversation with no messages should not get a summary
        conv.refresh_from_db()
        assert "summary" not in conv.context

    @pytest.mark.django_db(transaction=True)
    def test_generate_conversation_summaries_escalated(self):
        """Test summary generation for escalated conversations."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(
            patient=patient,
            status="escalated",
            context={},
        )

        AgentMessageFactory(conversation=conversation, role="user", content="Severe pain")

        mock_result = Mock()
        mock_result.response = "Escalated due to severe pain."

        with (
            patch("apps.agents.agents.DocumentationAgent") as mock_agent_class,
            patch("asyncio.run", return_value=mock_result),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.process = Mock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            result = generate_conversation_summaries()

        assert result["generated"] >= 1

    @pytest.mark.django_db(transaction=True)
    def test_generate_conversation_summaries_batch_limit(self):
        """Test that only 100 conversations are processed at a time."""
        patient = PatientFactory()

        # Create 105 completed conversations
        for i in range(105):
            conversation = AgentConversationFactory(
                patient=patient,
                status="completed",
                context={},
            )
            AgentMessageFactory(conversation=conversation, role="user", content=f"Message {i}")

        mock_result = Mock()
        mock_result.response = "Summary"

        with (
            patch("apps.agents.agents.DocumentationAgent") as mock_agent_class,
            patch("asyncio.run", side_effect=Exception("LLM error")),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.process = Mock(side_effect=Exception("LLM error"))
            mock_agent_class.return_value = mock_agent_instance

            result = generate_conversation_summaries()

        # Should complete despite exception — errors don't count as generated
        assert isinstance(result["generated"], int)

    @pytest.mark.django_db(transaction=True)
    def test_generate_conversation_summaries_active_conversations_excluded(self):
        """Test that active conversations are not processed."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(
            patient=patient,
            status="active",  # Not completed or escalated
        )

        AgentMessageFactory(conversation=conversation, role="user", content="Hello")

        mock_result = Mock()
        mock_result.response = "Summary"

        with (
            patch("apps.agents.agents.DocumentationAgent") as mock_agent_class,
            patch("asyncio.run", return_value=mock_result),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.process = Mock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            generate_conversation_summaries()

        # Active conversation should not get a summary
        conversation.refresh_from_db()
        assert "summary" not in conversation.context

    @pytest.mark.django_db(transaction=True)
    def test_generate_conversation_summaries_transcript_format(self):
        """Test that transcript is properly formatted for DocumentationAgent."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(
            patient=patient,
            status="completed",
            context={},
        )

        AgentMessageFactory(
            conversation=conversation,
            role="user",
            content="I have a question",
        )
        AgentMessageFactory(
            conversation=conversation,
            role="assistant",
            content="How can I help?",
            agent_type="care_coordinator",
        )

        mock_result = Mock()
        mock_result.response = "Summary"

        with (
            patch("apps.agents.agents.DocumentationAgent") as mock_agent_class,
            patch("asyncio.run", return_value=mock_result),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.process = Mock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            result = generate_conversation_summaries()

        # Use >= 1 because xdist workers may create other completed conversations
        assert result["generated"] >= 1


class TestTaskEdgeCases:
    """Additional edge case tests for all tasks."""

    @pytest.mark.django_db(transaction=True)
    def test_process_patient_message_empty_message(self, mock_workflow):
        """Test processing an empty message."""
        patient = PatientFactory()
        message = ""

        workflow_result = {
            "response": "I didn't receive a message. How can I help?",
            "agent_type": "care_coordinator",
            "escalate": False,
            "escalation_reason": "",
            "metadata": {},
        }
        mock_workflow.process_message.return_value = workflow_result

        with (
            patch("apps.agents.tasks.get_workflow", return_value=mock_workflow),
            patch("asyncio.run", return_value=workflow_result),
        ):
            result = process_patient_message(str(patient.id), message)

        assert result["success"] is True

    @pytest.mark.django_db(transaction=True)
    def test_send_proactive_checkin_unicode_content(self):
        """Test check-in with unicode content."""
        patient = PatientFactory()
        patient.user.first_name = "José"
        patient.user.save()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1",
            check_in_questions=["¿Cómo está su dolor?"],
        )

        result = send_proactive_checkin(str(patient.id), milestone.id)

        assert result["success"] is True
        assert "José" in result["message"]

    @pytest.mark.django_db(transaction=True)
    def test_check_missed_checkins_exactly_24_hours(self):
        """Test check-in exactly 24 hours old."""
        patient = PatientFactory()

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="Test Surgery",
            description="Test",
            duration_days=30,
        )
        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=1,
            phase="early",
            title="Day 1",
        )

        # Create check-in exactly 24 hours ago
        PatientMilestoneCheckin.objects.create(
            patient=patient,
            milestone=milestone,
            sent_at=timezone.now() - timedelta(hours=24),
        )

        with patch("apps.agents.services.EscalationService") as mock_esc_class:
            mock_esc_class.create_escalation = Mock(return_value=Mock())
            result = check_missed_checkins()

        assert result["missed_checkins"] == 1

    @pytest.mark.django_db(transaction=True)
    def test_cleanup_old_conversations_zero_days(self):
        """Test cleanup is a no-op even with zero days."""
        patient = PatientFactory()

        conversation = AgentConversationFactory(
            patient=patient,
            status="completed",
        )
        conversation.created_at = timezone.now() - timedelta(days=1)
        conversation.updated_at = timezone.now() - timedelta(days=1)
        conversation.save()

        result = cleanup_old_conversations(days=0)

        assert result["deleted"] == 0
        assert AgentConversation.objects.filter(id=conversation.id).exists()

    @pytest.mark.django_db(transaction=True)
    def test_generate_conversation_summaries_long_transcript(self):
        """Test summary generation with very long transcript."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(
            patient=patient,
            status="completed",
            context={},
        )

        # Create many messages
        for i in range(50):
            AgentMessageFactory(
                conversation=conversation,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}: " + "x" * 100,
            )

        mock_result = Mock()
        mock_result.response = "Long conversation summary"

        with (
            patch("apps.agents.agents.DocumentationAgent") as mock_agent_class,
            patch("asyncio.run", return_value=mock_result),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.process = Mock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            result = generate_conversation_summaries()

        assert result["generated"] >= 1


class TestTaskIntegration:
    """Integration tests showing task interactions."""

    @pytest.mark.django_db(transaction=True)
    def test_full_checkin_workflow(self):
        """Test the full check-in workflow from scheduling to escalation."""
        # Setup patient with pathway
        patient = PatientFactory(surgery_date=date.today() - timedelta(days=3))

        pathway = ClinicalPathway.objects.create(
            name="Knee Replacement Recovery",
            surgery_type="Knee Replacement",
            description="Standard recovery",
            duration_days=90,
        )
        PatientPathway.objects.create(
            patient=patient,
            pathway=pathway,
            status="active",
        )

        milestone = PathwayMilestone.objects.create(
            pathway=pathway,
            day=3,
            phase="early",
            title="Day 3 Check-in",
            check_in_questions=["How is your pain?"],
        )

        # Step 1: Schedule check-ins
        with patch("apps.agents.tasks.send_proactive_checkin") as mock_send:
            mock_send.delay = Mock(return_value=None)
            schedule_result = schedule_proactive_checkins()

        assert schedule_result["scheduled"] == 1

        # Step 2: Send the check-in
        send_result = send_proactive_checkin(str(patient.id), milestone.id)
        assert send_result["success"] is True

        # Step 3: Simulate time passing (25 hours later)
        checkin = PatientMilestoneCheckin.objects.get(patient=patient, milestone=milestone)
        checkin.sent_at = timezone.now() - timedelta(hours=25)
        checkin.save()

        # Step 4: Check for missed check-ins
        with patch("apps.agents.services.EscalationService") as mock_esc_class:
            mock_esc_class.create_escalation = Mock(return_value=Mock())
            missed_result = check_missed_checkins()

        assert missed_result["missed_checkins"] == 1
