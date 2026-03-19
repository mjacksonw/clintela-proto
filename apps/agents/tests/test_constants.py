"""Tests for agent constants."""

import pytest

from apps.agents import constants


class TestConstantsExist:
    """Tests that constants are properly defined."""

    def test_confidence_constants_exist(self):
        """Test confidence configuration constants exist."""
        assert hasattr(constants, "CONFIDENCE_BASE_SCORE")
        assert hasattr(constants, "CONFIDENCE_ESCALATION_THRESHOLD")
        assert constants.CONFIDENCE_ESCALATION_THRESHOLD == 0.70

    def test_conversation_limits_exist(self):
        """Test conversation limit constants exist."""
        assert hasattr(constants, "MAX_MESSAGE_LENGTH")
        assert hasattr(constants, "MAX_MESSAGES_PER_REQUEST")
        assert hasattr(constants, "MAX_CONVERSATION_HISTORY")

    def test_rate_limits_exist(self):
        """Test rate limit constants exist."""
        assert hasattr(constants, "RATE_LIMIT_MESSAGES_PER_MINUTE")
        assert hasattr(constants, "RATE_LIMIT_MESSAGES_PER_HOUR")
        assert hasattr(constants, "RATE_LIMIT_BURST_SIZE")

    def test_agent_types_exist(self):
        """Test agent type constants exist."""
        assert hasattr(constants, "AGENT_SUPERVISOR")
        assert hasattr(constants, "AGENT_CARE_COORDINATOR")
        assert hasattr(constants, "AGENT_NURSE_TRIAGE")
        assert constants.AGENT_SUPERVISOR == "supervisor"

    def test_specialist_agents_list(self):
        """Test specialist agents list exists and is populated."""
        assert hasattr(constants, "SPECIALIST_AGENTS")
        assert len(constants.SPECIALIST_AGENTS) > 0
        assert "specialist_cardiology" in constants.SPECIALIST_AGENTS

    def test_critical_keywords_exist(self):
        """Test critical keywords list exists."""
        assert hasattr(constants, "CRITICAL_KEYWORDS")
        assert len(constants.CRITICAL_KEYWORDS) > 0
        # Check some expected keywords
        keywords_str = " ".join(constants.CRITICAL_KEYWORDS).lower()
        assert "pain" in keywords_str
        assert "bleeding" in keywords_str or "blood" in keywords_str

    def test_escalation_severities_exist(self):
        """Test escalation severity constants exist."""
        assert hasattr(constants, "ESCALATION_SEVERITY_CRITICAL")
        assert hasattr(constants, "ESCALATION_SEVERITY_URGENT")
        assert hasattr(constants, "ESCALATION_SEVERITY_ROUTINE")
        assert hasattr(constants, "ESCALATION_SEVERITY_ORDER")
        assert len(constants.ESCALATION_SEVERITY_ORDER) == 3

    def test_llm_config_exists(self):
        """Test LLM configuration constants exist."""
        assert hasattr(constants, "LLM_TIMEOUT_SECONDS")
        assert hasattr(constants, "LLM_MAX_RETRIES")
        assert hasattr(constants, "LLM_RETRY_BACKOFF_MULTIPLIER")

    def test_conversation_statuses_exist(self):
        """Test conversation status constants exist."""
        assert hasattr(constants, "CONVERSATION_STATUS_ACTIVE")
        assert hasattr(constants, "CONVERSATION_STATUS_PAUSED")
        assert hasattr(constants, "CONVERSATION_STATUS_COMPLETED")
        assert hasattr(constants, "CONVERSATION_STATUS_ESCALATED")

    def test_recovery_phase_thresholds(self):
        """Test recovery phase thresholds exist and make sense."""
        assert hasattr(constants, "PHASE_EARLY_DAYS")
        assert hasattr(constants, "PHASE_MIDDLE_DAYS")
        assert constants.PHASE_EARLY_DAYS < constants.PHASE_MIDDLE_DAYS

    def test_hipaa_audit_retention(self):
        """Test audit log retention is HIPAA compliant (7+ years)."""
        assert hasattr(constants, "AUDIT_LOG_RETENTION_DAYS")
        assert constants.AUDIT_LOG_RETENTION_DAYS >= 2555  # 7 years
