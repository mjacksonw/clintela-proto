"""WebSocket input validation schemas."""

from typing import Literal

from pydantic import BaseModel, Field, validator


class ChatMessageValidator(BaseModel):
    """Validator for chat messages from WebSocket."""

    message: str = Field(..., min_length=1, max_length=2000)
    patient_id: str
    type: Literal["chat", "command", "status"] = Field(default="chat")

    @validator("message")
    def validate_message_content(self, v: str) -> str:
        """Validate message content."""
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        if len(v) > 2000:
            raise ValueError("Message too long (max 2000 characters)")
        return v


class EscalationAcknowledgementValidator(BaseModel):
    """Validator for escalation acknowledgement."""

    escalation_id: str
    clinician_id: int = Field(..., gt=0)
    notes: str = Field(default="", max_length=500)


class PatientContextValidator(BaseModel):
    """Validator for patient context requests."""

    patient_id: str
    include_history: bool = Field(default=True)
    history_limit: int = Field(default=10, ge=1, le=50)


class RateLimitConfig(BaseModel):
    """Rate limit configuration."""

    messages_per_minute: int = Field(default=30, ge=1, le=100)
    messages_per_hour: int = Field(default=300, ge=1, le=1000)
    burst_size: int = Field(default=10, ge=1, le=50)
