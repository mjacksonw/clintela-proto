"""Comprehensive tests for validators and schemas.

This module tests all Pydantic validators and Django Ninja schemas
for the agents app with 100% coverage target.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from apps.agents.schemas import (
    AgentRoutingRequest,
    AgentRoutingResponse,
    ChatHistoryResponse,
    ChatMessageItem,
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationContextRequest,
    ConversationContextResponse,
    DocumentationRequest,
    DocumentationResponse,
    EscalationListResponse,
    EscalationResponse,
)
from apps.agents.validators import (
    ChatMessageValidator,
    EscalationAcknowledgementValidator,
    PatientContextValidator,
    RateLimitConfig,
)


class TestChatMessageValidator:
    """Tests for ChatMessageValidator."""

    def test_valid_message(self):
        """Test valid message creation."""
        data = ChatMessageValidator(
            message="Hello, I have a question",
            patient_id="patient-123",
            type="chat",
        )
        assert data.message == "Hello, I have a question"
        assert data.patient_id == "patient-123"
        assert data.type == "chat"

    def test_message_with_whitespace_stripping(self):
        """Test that leading/trailing whitespace is stripped."""
        data = ChatMessageValidator(
            message="  Hello world  ",
            patient_id="patient-123",
            type="chat",
        )
        assert data.message == "Hello world"

    def test_message_with_only_whitespace_fails(self):
        """Test message with only whitespace fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageValidator(
                message="   ",
                patient_id="patient-123",
                type="chat",
            )
        assert "Message cannot be empty" in str(exc_info.value)

    def test_empty_message_fails(self):
        """Test empty message fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageValidator(
                message="",
                patient_id="patient-123",
                type="chat",
            )
        # Pydantic v2 produces "String should have at least 1 character"
        assert "at least 1 character" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()

    def test_message_at_max_length(self):
        """Test message at exactly 2000 characters."""
        long_message = "a" * 2000
        data = ChatMessageValidator(
            message=long_message,
            patient_id="patient-123",
            type="chat",
        )
        assert len(data.message) == 2000

    def test_message_exceeds_max_length(self):
        """Test message exceeding 2000 characters fails."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageValidator(
                message="a" * 2001,
                patient_id="patient-123",
                type="chat",
            )
        # Pydantic v2 produces "String should have at most 2000 characters"
        assert "at most" in str(exc_info.value).lower() or "too long" in str(exc_info.value).lower()

    def test_message_min_length_one_character(self):
        """Test single character message is valid."""
        data = ChatMessageValidator(
            message="X",
            patient_id="patient-123",
            type="chat",
        )
        assert data.message == "X"

    def test_message_with_unicode(self):
        """Test message with unicode characters."""
        data = ChatMessageValidator(
            message="Hello 👋 ¿Cómo estás? 日本語",
            patient_id="patient-123",
            type="chat",
        )
        assert "👋" in data.message

    def test_patient_id_required(self):
        """Test patient_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageValidator(
                message="Hello",
                type="chat",
            )
        assert "patient_id" in str(exc_info.value)

    def test_type_chat_valid(self):
        """Test type='chat' is valid."""
        data = ChatMessageValidator(
            message="Hello",
            patient_id="patient-123",
            type="chat",
        )
        assert data.type == "chat"

    def test_type_command_valid(self):
        """Test type='command' is valid."""
        data = ChatMessageValidator(
            message="/status",
            patient_id="patient-123",
            type="command",
        )
        assert data.type == "command"

    def test_type_status_valid(self):
        """Test type='status' is valid."""
        data = ChatMessageValidator(
            message="online",
            patient_id="patient-123",
            type="status",
        )
        assert data.type == "status"

    def test_type_invalid_fails(self):
        """Test invalid type fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageValidator(
                message="Hello",
                patient_id="patient-123",
                type="invalid_type",
            )
        assert "type" in str(exc_info.value)

    def test_default_type_is_chat(self):
        """Test default type is 'chat'."""
        data = ChatMessageValidator(
            message="Hello",
            patient_id="patient-123",
        )
        assert data.type == "chat"

    def test_patient_id_with_special_chars(self):
        """Test patient_id with special characters."""
        data = ChatMessageValidator(
            message="Hello",
            patient_id="patient_123-abc.ABC",
            type="chat",
        )
        assert data.patient_id == "patient_123-abc.ABC"


class TestEscalationAcknowledgementValidator:
    """Tests for EscalationAcknowledgementValidator."""

    def test_valid_escalation_acknowledgement(self):
        """Test valid escalation acknowledgement."""
        data = EscalationAcknowledgementValidator(
            escalation_id="esc-123",
            clinician_id=42,
            notes="Acknowledged and reviewing",
        )
        assert data.escalation_id == "esc-123"
        assert data.clinician_id == 42
        assert data.notes == "Acknowledged and reviewing"

    def test_clinician_id_required(self):
        """Test clinician_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            EscalationAcknowledgementValidator(
                escalation_id="esc-123",
            )
        assert "clinician_id" in str(exc_info.value)

    def test_clinician_id_must_be_positive(self):
        """Test clinician_id must be positive integer."""
        with pytest.raises(ValidationError) as exc_info:
            EscalationAcknowledgementValidator(
                escalation_id="esc-123",
                clinician_id=0,
            )
        assert "clinician_id" in str(exc_info.value)
        assert "greater than" in str(exc_info.value) or "Input should be greater than" in str(exc_info.value)

    def test_clinician_id_negative_fails(self):
        """Test negative clinician_id fails."""
        with pytest.raises(ValidationError) as exc_info:
            EscalationAcknowledgementValidator(
                escalation_id="esc-123",
                clinician_id=-1,
            )
        assert "clinician_id" in str(exc_info.value)

    def test_clinician_id_one_is_valid(self):
        """Test clinician_id=1 is valid (boundary)."""
        data = EscalationAcknowledgementValidator(
            escalation_id="esc-123",
            clinician_id=1,
        )
        assert data.clinician_id == 1

    def test_notes_default_empty_string(self):
        """Test notes defaults to empty string."""
        data = EscalationAcknowledgementValidator(
            escalation_id="esc-123",
            clinician_id=42,
        )
        assert data.notes == ""

    def test_notes_max_length(self):
        """Test notes at max length (500 chars)."""
        long_note = "a" * 500
        data = EscalationAcknowledgementValidator(
            escalation_id="esc-123",
            clinician_id=42,
            notes=long_note,
        )
        assert len(data.notes) == 500

    def test_notes_exceeds_max_length(self):
        """Test notes exceeding 500 characters fails."""
        with pytest.raises(ValidationError) as exc_info:
            EscalationAcknowledgementValidator(
                escalation_id="esc-123",
                clinician_id=42,
                notes="a" * 501,
            )
        assert "notes" in str(exc_info.value)

    def test_escalation_id_required(self):
        """Test escalation_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            EscalationAcknowledgementValidator(
                clinician_id=42,
            )
        assert "escalation_id" in str(exc_info.value)

    def test_clinician_id_type_coercion_int_from_str(self):
        """Test clinician_id can be coerced from string integer."""
        data = EscalationAcknowledgementValidator(
            escalation_id="esc-123",
            clinician_id="42",
        )
        assert data.clinician_id == 42
        assert isinstance(data.clinician_id, int)

    def test_clinician_id_float_coercion(self):
        """Test clinician_id coerced from float."""
        data = EscalationAcknowledgementValidator(
            escalation_id="esc-123",
            clinician_id=42.0,
        )
        assert data.clinician_id == 42

    def test_clinician_id_float_with_decimal_fails(self):
        """Test clinician_id with decimal fails."""
        with pytest.raises(ValidationError) as exc_info:
            EscalationAcknowledgementValidator(
                escalation_id="esc-123",
                clinician_id=42.5,
            )
        assert "clinician_id" in str(exc_info.value)


class TestPatientContextValidator:
    """Tests for PatientContextValidator."""

    def test_valid_patient_context(self):
        """Test valid patient context request."""
        data = PatientContextValidator(
            patient_id="patient-123",
            include_history=True,
            history_limit=25,
        )
        assert data.patient_id == "patient-123"
        assert data.include_history is True
        assert data.history_limit == 25

    def test_patient_id_required(self):
        """Test patient_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            PatientContextValidator()
        assert "patient_id" in str(exc_info.value)

    def test_include_history_defaults_true(self):
        """Test include_history defaults to True."""
        data = PatientContextValidator(
            patient_id="patient-123",
        )
        assert data.include_history is True

    def test_include_history_can_be_false(self):
        """Test include_history can be set to False."""
        data = PatientContextValidator(
            patient_id="patient-123",
            include_history=False,
        )
        assert data.include_history is False

    def test_history_limit_defaults_to_10(self):
        """Test history_limit defaults to 10."""
        data = PatientContextValidator(
            patient_id="patient-123",
        )
        assert data.history_limit == 10

    def test_history_limit_minimum_boundary(self):
        """Test history_limit minimum boundary (1)."""
        data = PatientContextValidator(
            patient_id="patient-123",
            history_limit=1,
        )
        assert data.history_limit == 1

    def test_history_limit_maximum_boundary(self):
        """Test history_limit maximum boundary (50)."""
        data = PatientContextValidator(
            patient_id="patient-123",
            history_limit=50,
        )
        assert data.history_limit == 50

    def test_history_limit_below_minimum_fails(self):
        """Test history_limit below 1 fails."""
        with pytest.raises(ValidationError) as exc_info:
            PatientContextValidator(
                patient_id="patient-123",
                history_limit=0,
            )
        assert "history_limit" in str(exc_info.value)

    def test_history_limit_above_maximum_fails(self):
        """Test history_limit above 50 fails."""
        with pytest.raises(ValidationError) as exc_info:
            PatientContextValidator(
                patient_id="patient-123",
                history_limit=51,
            )
        assert "history_limit" in str(exc_info.value)

    def test_history_limit_negative_fails(self):
        """Test negative history_limit fails."""
        with pytest.raises(ValidationError) as exc_info:
            PatientContextValidator(
                patient_id="patient-123",
                history_limit=-1,
            )
        assert "history_limit" in str(exc_info.value)

    def test_include_history_type_coercion(self):
        """Test include_history type coercion from string."""
        data = PatientContextValidator(
            patient_id="patient-123",
            include_history="true",
        )
        assert data.include_history is True

    def test_history_limit_type_coercion(self):
        """Test history_limit type coercion from string."""
        data = PatientContextValidator(
            patient_id="patient-123",
            history_limit="25",
        )
        assert data.history_limit == 25

    def test_history_limit_float_coercion(self):
        """Test history_limit coerced from float."""
        data = PatientContextValidator(
            patient_id="patient-123",
            history_limit=25.0,
        )
        assert data.history_limit == 25


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_valid_rate_limit_config(self):
        """Test valid rate limit configuration."""
        data = RateLimitConfig(
            messages_per_minute=30,
            messages_per_hour=300,
            burst_size=10,
        )
        assert data.messages_per_minute == 30
        assert data.messages_per_hour == 300
        assert data.burst_size == 10

    def test_default_values(self):
        """Test default values for rate limits."""
        data = RateLimitConfig()
        assert data.messages_per_minute == 30
        assert data.messages_per_hour == 300
        assert data.burst_size == 10

    def test_messages_per_minute_minimum(self):
        """Test messages_per_minute minimum boundary (1)."""
        data = RateLimitConfig(messages_per_minute=1)
        assert data.messages_per_minute == 1

    def test_messages_per_minute_maximum(self):
        """Test messages_per_minute maximum boundary (100)."""
        data = RateLimitConfig(messages_per_minute=100)
        assert data.messages_per_minute == 100

    def test_messages_per_minute_below_minimum_fails(self):
        """Test messages_per_minute below 1 fails."""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(messages_per_minute=0)
        assert "messages_per_minute" in str(exc_info.value)

    def test_messages_per_minute_above_maximum_fails(self):
        """Test messages_per_minute above 100 fails."""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(messages_per_minute=101)
        assert "messages_per_minute" in str(exc_info.value)

    def test_messages_per_hour_minimum(self):
        """Test messages_per_hour minimum boundary (1)."""
        data = RateLimitConfig(messages_per_hour=1)
        assert data.messages_per_hour == 1

    def test_messages_per_hour_maximum(self):
        """Test messages_per_hour maximum boundary (1000)."""
        data = RateLimitConfig(messages_per_hour=1000)
        assert data.messages_per_hour == 1000

    def test_messages_per_hour_below_minimum_fails(self):
        """Test messages_per_hour below 1 fails."""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(messages_per_hour=0)
        assert "messages_per_hour" in str(exc_info.value)

    def test_messages_per_hour_above_maximum_fails(self):
        """Test messages_per_hour above 1000 fails."""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(messages_per_hour=1001)
        assert "messages_per_hour" in str(exc_info.value)

    def test_burst_size_minimum(self):
        """Test burst_size minimum boundary (1)."""
        data = RateLimitConfig(burst_size=1)
        assert data.burst_size == 1

    def test_burst_size_maximum(self):
        """Test burst_size maximum boundary (50)."""
        data = RateLimitConfig(burst_size=50)
        assert data.burst_size == 50

    def test_burst_size_below_minimum_fails(self):
        """Test burst_size below 1 fails."""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(burst_size=0)
        assert "burst_size" in str(exc_info.value)

    def test_burst_size_above_maximum_fails(self):
        """Test burst_size above 50 fails."""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(burst_size=51)
        assert "burst_size" in str(exc_info.value)

    def test_type_coercion_from_string(self):
        """Test type coercion from string values."""
        data = RateLimitConfig(
            messages_per_minute="45",
            messages_per_hour="500",
            burst_size="15",
        )
        assert data.messages_per_minute == 45
        assert data.messages_per_hour == 500
        assert data.burst_size == 15

    def test_type_coercion_from_float(self):
        """Test type coercion from float values."""
        data = RateLimitConfig(
            messages_per_minute=45.0,
            messages_per_hour=500.0,
            burst_size=15.0,
        )
        assert data.messages_per_minute == 45
        assert data.messages_per_hour == 500
        assert data.burst_size == 15


class TestChatMessageRequestSchema:
    """Tests for ChatMessageRequest schema."""

    def test_valid_request(self):
        """Test valid chat message request."""
        data = ChatMessageRequest(message="Hello world")
        assert data.message == "Hello world"

    def test_message_required(self):
        """Test message field is required."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageRequest()
        assert "message" in str(exc_info.value)

    def test_empty_message_valid(self):
        """Test empty message is valid (schema-level only)."""
        data = ChatMessageRequest(message="")
        assert data.message == ""

    def test_message_with_special_chars(self):
        """Test message with special characters."""
        data = ChatMessageRequest(message="Hello! @#$%^&*() 🎉")
        assert data.message == "Hello! @#$%^&*() 🎉"


class TestChatMessageResponseSchema:
    """Tests for ChatMessageResponse schema."""

    def test_valid_response(self):
        """Test valid chat message response."""
        data = ChatMessageResponse(
            response="Hello, how can I help?",
            agent_type="care_coordinator",
            escalate=False,
            escalation_reason="",
            conversation_id="conv-123",
        )
        assert data.response == "Hello, how can I help?"
        assert data.agent_type == "care_coordinator"
        assert data.escalate is False
        assert data.escalation_reason == ""
        assert data.conversation_id == "conv-123"

    def test_escalation_reason_optional(self):
        """Test escalation_reason has default empty string."""
        data = ChatMessageResponse(
            response="Escalating...",
            agent_type="supervisor",
            escalate=True,
            conversation_id="conv-123",
        )
        assert data.escalation_reason == ""

    def test_escalate_true(self):
        """Test escalate can be True."""
        data = ChatMessageResponse(
            response="I need to escalate this",
            agent_type="nurse_triage",
            escalate=True,
            escalation_reason="Critical symptom reported",
            conversation_id="conv-123",
        )
        assert data.escalate is True
        assert data.escalation_reason == "Critical symptom reported"

    def test_required_fields(self):
        """Test all required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageResponse()
        error_str = str(exc_info.value)
        assert "response" in error_str
        assert "agent_type" in error_str
        assert "escalate" in error_str
        assert "conversation_id" in error_str


class TestChatMessageItemSchema:
    """Tests for ChatMessageItem schema."""

    def test_valid_item(self):
        """Test valid chat message item."""
        now = datetime.now()
        data = ChatMessageItem(
            role="user",
            content="Hello",
            agent_type="",
            created_at=now,
        )
        assert data.role == "user"
        assert data.content == "Hello"
        assert data.agent_type == ""
        assert data.created_at == now

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageItem()
        error_str = str(exc_info.value)
        assert "role" in error_str
        assert "content" in error_str
        assert "created_at" in error_str

    def test_agent_type_defaults_empty(self):
        """Test agent_type defaults to empty string."""
        data = ChatMessageItem(
            role="assistant",
            content="Hi there",
            created_at=datetime.now(),
        )
        assert data.agent_type == ""

    def test_various_roles(self):
        """Test various role values."""
        for role in ["user", "assistant", "system", "tool"]:
            data = ChatMessageItem(
                role=role,
                content="Test",
                created_at=datetime.now(),
            )
            assert data.role == role


class TestChatHistoryResponseSchema:
    """Tests for ChatHistoryResponse schema."""

    def test_valid_response(self):
        """Test valid chat history response."""
        now = datetime.now()
        messages = [
            ChatMessageItem(role="user", content="Hello", created_at=now),
            ChatMessageItem(role="assistant", content="Hi!", agent_type="care_coordinator", created_at=now),
        ]
        data = ChatHistoryResponse(
            messages=messages,
            total=2,
            page=1,
            page_size=20,
        )
        assert len(data.messages) == 2
        assert data.total == 2
        assert data.page == 1
        assert data.page_size == 20

    def test_empty_messages_list(self):
        """Test empty messages list."""
        data = ChatHistoryResponse(
            messages=[],
            total=0,
            page=1,
            page_size=20,
        )
        assert data.messages == []
        assert data.total == 0

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ChatHistoryResponse()
        error_str = str(exc_info.value)
        assert "messages" in error_str
        assert "total" in error_str
        assert "page" in error_str
        assert "page_size" in error_str

    def test_pagination_values(self):
        """Test various pagination values."""
        data = ChatHistoryResponse(
            messages=[],
            total=100,
            page=5,
            page_size=10,
        )
        assert data.page == 5
        assert data.page_size == 10


class TestEscalationResponseSchema:
    """Tests for EscalationResponse schema."""

    def test_valid_response(self):
        """Test valid escalation response."""
        now = datetime.now()
        data = EscalationResponse(
            id="esc-123",
            patient_id="patient-456",
            patient_name="John Doe",
            reason="Severe pain",
            severity="high",
            status="pending",
            created_at=now,
            conversation_summary="Patient reported 9/10 pain",
        )
        assert data.id == "esc-123"
        assert data.patient_id == "patient-456"
        assert data.patient_name == "John Doe"
        assert data.reason == "Severe pain"
        assert data.severity == "high"
        assert data.status == "pending"
        assert data.created_at == now
        assert data.conversation_summary == "Patient reported 9/10 pain"

    def test_conversation_summary_optional(self):
        """Test conversation_summary defaults to empty string."""
        now = datetime.now()
        data = EscalationResponse(
            id="esc-123",
            patient_id="patient-456",
            patient_name="John Doe",
            reason="Severe pain",
            severity="high",
            status="pending",
            created_at=now,
        )
        assert data.conversation_summary == ""

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError) as exc_info:
            EscalationResponse()
        error_str = str(exc_info.value)
        assert "id" in error_str
        assert "patient_id" in error_str
        assert "patient_name" in error_str
        assert "reason" in error_str
        assert "severity" in error_str
        assert "status" in error_str
        assert "created_at" in error_str

    def test_various_severities(self):
        """Test various severity values."""
        now = datetime.now()
        for severity in ["low", "medium", "high", "critical", "red", "yellow", "green"]:
            data = EscalationResponse(
                id="esc-123",
                patient_id="patient-456",
                patient_name="John Doe",
                reason="Test",
                severity=severity,
                status="pending",
                created_at=now,
            )
            assert data.severity == severity


class TestEscalationListResponseSchema:
    """Tests for EscalationListResponse schema."""

    def test_valid_response(self):
        """Test valid escalation list response."""
        now = datetime.now()
        escalations = [
            EscalationResponse(
                id="esc-1",
                patient_id="p1",
                patient_name="Patient One",
                reason="Pain",
                severity="high",
                status="pending",
                created_at=now,
            ),
            EscalationResponse(
                id="esc-2",
                patient_id="p2",
                patient_name="Patient Two",
                reason="Fever",
                severity="medium",
                status="acknowledged",
                created_at=now,
            ),
        ]
        data = EscalationListResponse(
            escalations=escalations,
            total=2,
        )
        assert len(data.escalations) == 2
        assert data.total == 2

    def test_empty_escalations_list(self):
        """Test empty escalations list."""
        data = EscalationListResponse(
            escalations=[],
            total=0,
        )
        assert data.escalations == []
        assert data.total == 0

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError) as exc_info:
            EscalationListResponse()
        error_str = str(exc_info.value)
        assert "escalations" in error_str
        assert "total" in error_str


class TestAgentRoutingRequestSchema:
    """Tests for AgentRoutingRequest schema."""

    def test_valid_request(self):
        """Test valid agent routing request."""
        data = AgentRoutingRequest(
            message="I have chest pain",
            patient_id="patient-123",
            conversation_id="conv-456",
        )
        assert data.message == "I have chest pain"
        assert data.patient_id == "patient-123"
        assert data.conversation_id == "conv-456"

    def test_conversation_id_optional(self):
        """Test conversation_id is optional."""
        data = AgentRoutingRequest(
            message="Hello",
            patient_id="patient-123",
        )
        assert data.conversation_id is None

    def test_conversation_id_explicit_none(self):
        """Test conversation_id can be explicitly None."""
        data = AgentRoutingRequest(
            message="Hello",
            patient_id="patient-123",
            conversation_id=None,
        )
        assert data.conversation_id is None

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError) as exc_info:
            AgentRoutingRequest()
        error_str = str(exc_info.value)
        assert "message" in error_str
        assert "patient_id" in error_str


class TestAgentRoutingResponseSchema:
    """Tests for AgentRoutingResponse schema."""

    def test_valid_response(self):
        """Test valid agent routing response."""
        data = AgentRoutingResponse(
            agent="nurse_triage",
            urgency="urgent",
            escalate_to_human=True,
            reasoning="Patient reports severe symptoms",
            context_to_pass="Chest pain, 9/10 severity",
        )
        assert data.agent == "nurse_triage"
        assert data.urgency == "urgent"
        assert data.escalate_to_human is True
        assert data.reasoning == "Patient reports severe symptoms"
        assert data.context_to_pass == "Chest pain, 9/10 severity"

    def test_context_to_pass_optional(self):
        """Test context_to_pass defaults to empty string."""
        data = AgentRoutingResponse(
            agent="care_coordinator",
            urgency="routine",
            escalate_to_human=False,
            reasoning="General question",
        )
        assert data.context_to_pass == ""

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError) as exc_info:
            AgentRoutingResponse()
        error_str = str(exc_info.value)
        assert "agent" in error_str
        assert "urgency" in error_str
        assert "escalate_to_human" in error_str
        assert "reasoning" in error_str

    def test_various_agents(self):
        """Test various agent values."""
        for agent in ["supervisor", "care_coordinator", "nurse_triage", "documentation"]:
            data = AgentRoutingResponse(
                agent=agent,
                urgency="routine",
                escalate_to_human=False,
                reasoning="Test",
            )
            assert data.agent == agent

    def test_various_urgencies(self):
        """Test various urgency values."""
        for urgency in ["routine", "urgent", "critical", "low", "medium", "high"]:
            data = AgentRoutingResponse(
                agent="supervisor",
                urgency=urgency,
                escalate_to_human=False,
                reasoning="Test",
            )
            assert data.urgency == urgency


class TestConversationContextRequestSchema:
    """Tests for ConversationContextRequest schema."""

    def test_valid_request(self):
        """Test valid conversation context request."""
        data = ConversationContextRequest(
            patient_id="patient-123",
            include_history=True,
            history_limit=20,
        )
        assert data.patient_id == "patient-123"
        assert data.include_history is True
        assert data.history_limit == 20

    def test_defaults(self):
        """Test default values."""
        data = ConversationContextRequest(
            patient_id="patient-123",
        )
        assert data.include_history is True
        assert data.history_limit == 10

    def test_include_history_false(self):
        """Test include_history can be False."""
        data = ConversationContextRequest(
            patient_id="patient-123",
            include_history=False,
        )
        assert data.include_history is False

    def test_patient_id_required(self):
        """Test patient_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationContextRequest()
        assert "patient_id" in str(exc_info.value)


class TestConversationContextResponseSchema:
    """Tests for ConversationContextResponse schema."""

    def test_valid_response(self):
        """Test valid conversation context response."""
        data = ConversationContextResponse(
            patient={"id": "p1", "name": "John Doe"},
            pathway={"id": "path-1", "name": "Recovery"},
            conversation_history=[{"role": "user", "content": "Hello"}],
            recent_symptoms=["pain", "fatigue"],
        )
        assert data.patient == {"id": "p1", "name": "John Doe"}
        assert data.pathway == {"id": "path-1", "name": "Recovery"}
        assert data.conversation_history == [{"role": "user", "content": "Hello"}]
        assert data.recent_symptoms == ["pain", "fatigue"]

    def test_defaults(self):
        """Test default values."""
        data = ConversationContextResponse(
            patient={},
            pathway={},
        )
        assert data.conversation_history == []
        assert data.recent_symptoms == []

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationContextResponse()
        error_str = str(exc_info.value)
        assert "patient" in error_str
        assert "pathway" in error_str

    def test_empty_lists(self):
        """Test explicitly empty lists."""
        data = ConversationContextResponse(
            patient={},
            pathway={},
            conversation_history=[],
            recent_symptoms=[],
        )
        assert data.conversation_history == []
        assert data.recent_symptoms == []


class TestDocumentationRequestSchema:
    """Tests for DocumentationRequest schema."""

    def test_valid_request(self):
        """Test valid documentation request."""
        data = DocumentationRequest(conversation_id="conv-123")
        assert data.conversation_id == "conv-123"

    def test_conversation_id_required(self):
        """Test conversation_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentationRequest()
        assert "conversation_id" in str(exc_info.value)

    def test_various_conversation_ids(self):
        """Test various conversation ID formats."""
        for conv_id in ["abc-123", "CONV_456", "uuid-789-test"]:
            data = DocumentationRequest(conversation_id=conv_id)
            assert data.conversation_id == conv_id


class TestDocumentationResponseSchema:
    """Tests for DocumentationResponse schema."""

    def test_valid_response(self):
        """Test valid documentation response."""
        data = DocumentationResponse(
            summary="Patient reported mild pain",
            assessment="Stable condition",
            actions_taken=["Provided reassurance", "Scheduled follow-up"],
            follow_up_required="Yes, in 3 days",
            notes="Patient in good spirits",
        )
        assert data.summary == "Patient reported mild pain"
        assert data.assessment == "Stable condition"
        assert data.actions_taken == ["Provided reassurance", "Scheduled follow-up"]
        assert data.follow_up_required == "Yes, in 3 days"
        assert data.notes == "Patient in good spirits"

    def test_required_fields(self):
        """Test all fields are required."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentationResponse()
        error_str = str(exc_info.value)
        assert "summary" in error_str
        assert "assessment" in error_str
        assert "actions_taken" in error_str
        assert "follow_up_required" in error_str
        assert "notes" in error_str

    def test_empty_actions_list(self):
        """Test empty actions_taken list."""
        data = DocumentationResponse(
            summary="Summary",
            assessment="Assessment",
            actions_taken=[],
            follow_up_required="No",
            notes="Notes",
        )
        assert data.actions_taken == []

    def test_single_action(self):
        """Test single action in list."""
        data = DocumentationResponse(
            summary="Summary",
            assessment="Assessment",
            actions_taken=["Single action"],
            follow_up_required="No",
            notes="Notes",
        )
        assert data.actions_taken == ["Single action"]


class TestEdgeCasesAndTypeCoercion:
    """Tests for edge cases and type coercion across all schemas."""

    def test_datetime_parsing_from_string(self):
        """Test datetime parsing from ISO string."""
        iso_string = "2024-01-15T10:30:00"
        data = ChatMessageItem(
            role="user",
            content="Hello",
            created_at=iso_string,
        )
        assert isinstance(data.created_at, datetime)
        assert data.created_at.year == 2024
        assert data.created_at.month == 1
        assert data.created_at.day == 15

    def test_datetime_with_timezone(self):
        """Test datetime with timezone info."""
        iso_string = "2024-01-15T10:30:00+00:00"
        data = ChatMessageItem(
            role="user",
            content="Hello",
            created_at=iso_string,
        )
        assert isinstance(data.created_at, datetime)

    def test_invalid_datetime_fails(self):
        """Test invalid datetime string fails."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageItem(
                role="user",
                content="Hello",
                created_at="not-a-date",
            )
        assert "created_at" in str(exc_info.value)

    def test_nested_escalation_in_list(self):
        """Test nested escalation responses in list."""
        now = datetime.now()
        escalations = [
            {
                "id": "esc-1",
                "patient_id": "p1",
                "patient_name": "Patient One",
                "reason": "Pain",
                "severity": "high",
                "status": "pending",
                "created_at": now,
            }
        ]
        data = EscalationListResponse(
            escalations=escalations,
            total=1,
        )
        assert len(data.escalations) == 1
        assert isinstance(data.escalations[0], EscalationResponse)

    def test_nested_message_in_history(self):
        """Test nested chat messages in history."""
        now = datetime.now()
        messages = [
            {
                "role": "user",
                "content": "Hello",
                "created_at": now,
            }
        ]
        data = ChatHistoryResponse(
            messages=messages,
            total=1,
            page=1,
            page_size=20,
        )
        assert len(data.messages) == 1
        assert isinstance(data.messages[0], ChatMessageItem)

    def test_very_long_strings(self):
        """Test handling of very long strings."""
        long_text = "a" * 10000
        data = ChatMessageRequest(message=long_text)
        assert data.message == long_text

    def test_unicode_in_all_string_fields(self):
        """Test unicode handling across schemas."""
        unicode_text = "Hello 👋 🌍 ñ 中文 العربية 🎉"

        # Test in validators
        chat_data = ChatMessageValidator(
            message=unicode_text,
            patient_id="patient-日本",
            type="chat",
        )
        assert unicode_text in chat_data.message

        # Test in schemas
        request_data = ChatMessageRequest(message=unicode_text)
        assert request_data.message == unicode_text

        response_data = ChatMessageResponse(
            response=unicode_text,
            agent_type="care_coordinator",
            escalate=False,
            conversation_id="conv-中文",
        )
        assert response_data.response == unicode_text

    def test_none_values_in_optional_fields(self):
        """Test None values in optional fields."""
        data = AgentRoutingRequest(
            message="Hello",
            patient_id="p1",
            conversation_id=None,
        )
        assert data.conversation_id is None

    def test_boolean_coercion(self):
        """Test boolean coercion from various inputs."""
        # From strings
        data1 = ConversationContextRequest(
            patient_id="p1",
            include_history="true",
        )
        assert data1.include_history is True

        data2 = ConversationContextRequest(
            patient_id="p1",
            include_history="false",
        )
        assert data2.include_history is False

        # From integers
        data3 = ConversationContextRequest(
            patient_id="p1",
            include_history=1,
        )
        assert data3.include_history is True

        data4 = ConversationContextRequest(
            patient_id="p1",
            include_history=0,
        )
        assert data4.include_history is False


class TestSchemaDictConversion:
    """Tests for converting schemas to dictionaries."""

    def test_chat_message_response_to_dict(self):
        """Test ChatMessageResponse dict conversion."""
        data = ChatMessageResponse(
            response="Hello",
            agent_type="care_coordinator",
            escalate=False,
            conversation_id="conv-123",
        )
        d = data.dict()
        assert d["response"] == "Hello"
        assert d["agent_type"] == "care_coordinator"
        assert d["escalate"] is False

    def test_escalation_response_to_dict(self):
        """Test EscalationResponse dict conversion."""
        now = datetime.now()
        data = EscalationResponse(
            id="esc-123",
            patient_id="p1",
            patient_name="John",
            reason="Pain",
            severity="high",
            status="pending",
            created_at=now,
        )
        d = data.dict()
        assert d["id"] == "esc-123"
        assert d["patient_name"] == "John"
        assert isinstance(d["created_at"], datetime)

    def test_nested_schema_dict_conversion(self):
        """Test nested schema dict conversion."""
        now = datetime.now()
        item = ChatMessageItem(
            role="user",
            content="Hello",
            created_at=now,
        )
        history = ChatHistoryResponse(
            messages=[item],
            total=1,
            page=1,
            page_size=20,
        )
        d = history.dict()
        assert d["total"] == 1
        assert len(d["messages"]) == 1
        assert d["messages"][0]["role"] == "user"

    def test_json_conversion(self):
        """Test JSON serialization."""
        import json

        data = ChatMessageResponse(
            response="Hello",
            agent_type="care_coordinator",
            escalate=False,
            conversation_id="conv-123",
        )
        json_str = data.json()
        parsed = json.loads(json_str)
        assert parsed["response"] == "Hello"
        assert parsed["escalate"] is False


class TestValidationErrorMessages:
    """Tests for validation error message content."""

    def test_single_field_error(self):
        """Test single field validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageValidator(
                message="",
                patient_id="p1",
                type="chat",
            )
        error = exc_info.value
        assert "message" in str(error)

    def test_multiple_field_errors(self):
        """Test multiple field validation errors."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageValidator(message="")
        error_str = str(exc_info.value)
        assert "message" in error_str

    def test_error_contains_location(self):
        """Test error contains field location."""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(messages_per_minute=0)
        errors = exc_info.value.errors()
        assert any("messages_per_minute" in str(e) for e in errors)

    def test_error_types(self):
        """Test different error types."""
        # Missing field
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageRequest()
        assert "message" in str(exc_info.value)

        # Type error
        with pytest.raises(ValidationError) as exc_info:
            EscalationAcknowledgementValidator(
                escalation_id="esc-1",
                clinician_id="not-an-int",
            )
        assert "clinician_id" in str(exc_info.value)

        # Constraint error
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(messages_per_minute=-1)
        assert "messages_per_minute" in str(exc_info.value)
