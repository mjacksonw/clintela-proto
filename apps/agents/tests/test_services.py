"""Tests for agent services."""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from apps.agents.agents import calculate_confidence_score


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
