"""Pydantic schemas for agent API."""

from datetime import datetime
from typing import Any

from ninja import Schema


class ChatMessageRequest(Schema):
    """Request schema for sending a chat message."""

    message: str


class ChatMessageResponse(Schema):
    """Response schema for chat message."""

    response: str
    agent_type: str
    escalate: bool
    escalation_reason: str = ""
    conversation_id: str


class ChatMessageItem(Schema):
    """Individual chat message in history."""

    role: str
    content: str
    agent_type: str = ""
    created_at: datetime


class ChatHistoryResponse(Schema):
    """Response schema for chat history."""

    messages: list[ChatMessageItem]
    total: int
    page: int
    page_size: int


class EscalationResponse(Schema):
    """Individual escalation item."""

    id: str
    patient_id: str
    patient_name: str
    reason: str
    severity: str
    status: str
    created_at: datetime
    conversation_summary: str = ""


class EscalationListResponse(Schema):
    """Response schema for escalation list."""

    escalations: list[EscalationResponse]
    total: int


class AgentRoutingRequest(Schema):
    """Request schema for agent routing (internal)."""

    message: str
    patient_id: str
    conversation_id: str | None = None


class AgentRoutingResponse(Schema):
    """Response schema for agent routing."""

    agent: str
    urgency: str
    escalate_to_human: bool
    reasoning: str
    context_to_pass: str = ""


class ConversationContextRequest(Schema):
    """Request schema for getting conversation context."""

    patient_id: str
    include_history: bool = True
    history_limit: int = 10


class ConversationContextResponse(Schema):
    """Response schema for conversation context."""

    patient: dict[str, Any]
    pathway: dict[str, Any]
    conversation_history: list[dict[str, Any]] = []
    recent_symptoms: list[str] = []


class DocumentationRequest(Schema):
    """Request schema for generating documentation."""

    conversation_id: str


class DocumentationResponse(Schema):
    """Response schema for documentation."""

    summary: str
    assessment: str
    actions_taken: list[str]
    follow_up_required: str
    notes: str
