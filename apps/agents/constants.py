"""Constants and configuration for agent system."""

from typing import Final

# =============================================================================
# Confidence Score Configuration
# =============================================================================

CONFIDENCE_BASE_SCORE: Final[float] = 0.85
CONFIDENCE_STOP_BONUS: Final[float] = 0.05
CONFIDENCE_LENGTH_PENALTY: Final[float] = -0.10
CONFIDENCE_SHORT_PENALTY: Final[float] = -0.15
CONFIDENCE_LONG_PENALTY: Final[float] = -0.05
CONFIDENCE_CRITICAL_PENALTY: Final[float] = -0.30
CONFIDENCE_NURSE_TRIAGE_ADJUSTMENT: Final[float] = -0.05

CONFIDENCE_ESCALATION_THRESHOLD: Final[float] = 0.70

# =============================================================================
# Response Length Thresholds
# =============================================================================

SHORT_RESPONSE_THRESHOLD: Final[int] = 20
LONG_RESPONSE_THRESHOLD: Final[int] = 2000

# =============================================================================
# Conversation Limits
# =============================================================================

MAX_MESSAGE_LENGTH: Final[int] = 2000
MAX_MESSAGES_PER_REQUEST: Final[int] = 10
MAX_CONVERSATION_HISTORY: Final[int] = 50

# =============================================================================
# Rate Limiting
# =============================================================================

RATE_LIMIT_MESSAGES_PER_MINUTE: Final[int] = 30
RATE_LIMIT_MESSAGES_PER_HOUR: Final[int] = 300
RATE_LIMIT_BURST_SIZE: Final[int] = 10

# =============================================================================
# LLM Configuration
# =============================================================================

LLM_TIMEOUT_SECONDS: Final[int] = 30
LLM_MAX_RETRIES: Final[int] = 3
LLM_RETRY_BACKOFF_MULTIPLIER: Final[int] = 2
LLM_RETRY_MIN_SECONDS: Final[int] = 2
LLM_RETRY_MAX_SECONDS: Final[int] = 10

# Default temperature by agent type
LLM_TEMPERATURE_SUPERVISOR: Final[float] = 0.5
LLM_TEMPERATURE_CARE_COORDINATOR: Final[float] = 0.8
LLM_TEMPERATURE_NURSE_TRIAGE: Final[float] = 0.5
LLM_TEMPERATURE_DOCUMENTATION: Final[float] = 0.3

# Default max tokens
LLM_MAX_TOKENS_DEFAULT: Final[int] = 1000
LLM_MAX_TOKENS_DOCUMENTATION: Final[int] = 2000

# =============================================================================
# Escalation Severity Levels
# =============================================================================

ESCALATION_SEVERITY_CRITICAL: Final[str] = "critical"
ESCALATION_SEVERITY_URGENT: Final[str] = "urgent"
ESCALATION_SEVERITY_ROUTINE: Final[str] = "routine"

ESCALATION_SEVERITY_ORDER: Final[list[str]] = [
    ESCALATION_SEVERITY_ROUTINE,
    ESCALATION_SEVERITY_URGENT,
    ESCALATION_SEVERITY_CRITICAL,
]

# =============================================================================
# Agent Types
# =============================================================================

AGENT_SUPERVISOR: Final[str] = "supervisor"
AGENT_CARE_COORDINATOR: Final[str] = "care_coordinator"
AGENT_NURSE_TRIAGE: Final[str] = "nurse_triage"
AGENT_DOCUMENTATION: Final[str] = "documentation"

AGENT_SPECIALIST_CARDIOLOGY: Final[str] = "specialist_cardiology"
AGENT_SPECIALIST_SOCIAL_WORK: Final[str] = "specialist_social_work"
AGENT_SPECIALIST_NUTRITION: Final[str] = "specialist_nutrition"
AGENT_SPECIALIST_PT_REHAB: Final[str] = "specialist_pt_rehab"
AGENT_SPECIALIST_PALLIATIVE: Final[str] = "specialist_palliative"
AGENT_SPECIALIST_PHARMACY: Final[str] = "specialist_pharmacy"

SPECIALIST_AGENTS: Final[list[str]] = [
    AGENT_SPECIALIST_CARDIOLOGY,
    AGENT_SPECIALIST_SOCIAL_WORK,
    AGENT_SPECIALIST_NUTRITION,
    AGENT_SPECIALIST_PT_REHAB,
    AGENT_SPECIALIST_PALLIATIVE,
    AGENT_SPECIALIST_PHARMACY,
]

# =============================================================================
# Conversation Status
# =============================================================================

CONVERSATION_STATUS_ACTIVE: Final[str] = "active"
CONVERSATION_STATUS_PAUSED: Final[str] = "paused"
CONVERSATION_STATUS_COMPLETED: Final[str] = "completed"
CONVERSATION_STATUS_ESCALATED: Final[str] = "escalated"

# =============================================================================
# Critical Keywords for Auto-Escalation
# =============================================================================

CRITICAL_KEYWORDS: Final[list[str]] = [
    "pain 8",
    "pain 9",
    "pain 10",
    "severe pain",
    "unbearable pain",
    "intense pain",
    "bleeding",
    "blood",
    "hemorrhage",
    "hemorrhaging",
    "fever 102",
    "fever 103",
    "fever 104",
    "high fever",
    "chest pain",
    "heart attack",
    "cardiac arrest",
    "can't breathe",
    "breathing difficulty",
    "shortness of breath",
    "difficulty breathing",
    "wheezing",
    "struggling to breathe",
    "unconscious",
    "passed out",
    "fainted",
    "blackout",
    "vomiting blood",
    "coughing blood",
    "blood in vomit",
    "allergic reaction",
    "anaphylaxis",
    "swelling throat",
    "suicide",
    "kill myself",
    "end my life",
]

# =============================================================================
# Support Group Configuration
# =============================================================================

ENABLE_SUPPORT_GROUP: Final[bool] = True

# Distress keywords for support group (supplement CRITICAL_KEYWORDS)
SUPPORT_GROUP_DISTRESS_KEYWORDS: Final[list[str]] = [
    "i don't want to be here anymore",
    "what's the point",
    "i give up",
    "nobody cares",
    "end it all",
    "can't do this anymore",
    "want to die",
    "no reason to live",
    "better off without me",
    "hopeless",
    "i can't take it",
    "wish i was dead",
]

# Timing constants for staggered delivery
SG_FOLLOWUP_DELAY_MIN: Final[int] = 30  # seconds
SG_FOLLOWUP_DELAY_MAX: Final[int] = 180
SG_REACTION_DELAY_MIN: Final[int] = 15
SG_REACTION_DELAY_MAX: Final[int] = 30
SG_CELEBRATION_DELAY_MIN: Final[int] = 30
SG_CELEBRATION_DELAY_MAX: Final[int] = 60

# Persona memory
SG_MEMORY_SUMMARIZE_EVERY: Final[int] = 10  # messages
SG_MEMORY_TOKEN_BUDGET: Final[int] = 300  # per persona

# Absence detection
SG_ABSENCE_THRESHOLD_DAYS: Final[int] = 2

# Rate limiting for support group WS consumer
SG_RATE_LIMIT_SECONDS: Final[int] = 3  # min seconds between messages

# LLM settings
LLM_TEMPERATURE_SUPPORT_GROUP: Final[float] = 0.85
LLM_MAX_TOKENS_SUPPORT_GROUP: Final[int] = 500
LLM_MAX_TOKENS_ROUTER: Final[int] = 300

# Context window
SG_CONVERSATION_HISTORY_LIMIT: Final[int] = 10  # last N messages for context

# =============================================================================
# Recovery Phase Thresholds
# =============================================================================

PHASE_EARLY_DAYS: Final[int] = 3
PHASE_MIDDLE_DAYS: Final[int] = 14

# =============================================================================
# Audit Logging
# =============================================================================

AUDIT_LOG_RETENTION_DAYS: Final[int] = 2555  # 7 years for HIPAA

# =============================================================================
# Celery Task Configuration
# =============================================================================

CELERY_TASK_MAX_RETRIES: Final[int] = 3
CELERY_TASK_RETRY_BACKOFF: Final[bool] = True

# =============================================================================
# WebSocket Configuration
# =============================================================================

WEBSOCKET_HEARTBEAT_INTERVAL: Final[int] = 30
WEBSOCKET_RECONNECT_DELAY: Final[int] = 5
