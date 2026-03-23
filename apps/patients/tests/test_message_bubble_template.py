"""Tests for the message bubble template component.

Verifies that the low-confidence disclaimer uses care-philosophy-aligned
language (never "contact your care team" — Clintela IS the care team).
"""

import pytest
from django.template.loader import render_to_string

from apps.agents.models import AgentMessage
from apps.agents.tests.factories import AgentConversationFactory, AgentMessageFactory, PatientFactory


@pytest.mark.django_db
class TestMessageBubbleCarePhilosophy:
    """Verify the message bubble never uses 'care team' brush-off language."""

    def _render_bubble(self, message: AgentMessage) -> str:
        """Render the message bubble partial for *message*."""
        return render_to_string(
            "components/_message_bubble.html",
            {"message": message},
        )

    def test_low_confidence_uses_nurse_escalation_language(self):
        """Low-confidence messages should say 'let me involve a nurse', not
        'consider reaching out to your care team'."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)
        msg = AgentMessageFactory(
            conversation=conversation,
            role="assistant",
            confidence_score=0.3,  # well below 0.6 threshold
        )

        html = self._render_bubble(msg)

        # Must contain the new care-philosophy language
        assert "let me involve a nurse" in html
        # Must NOT contain the old brush-off language
        assert "care team" not in html
        assert "consider reaching out" not in html

    def test_high_confidence_hides_disclaimer(self):
        """Messages with confidence >= 0.6 should not show any disclaimer."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)
        msg = AgentMessageFactory(
            conversation=conversation,
            role="assistant",
            confidence_score=0.85,
        )

        html = self._render_bubble(msg)

        assert "let me involve a nurse" not in html
        assert "care team" not in html

    def test_no_confidence_score_hides_disclaimer(self):
        """Messages without a confidence score should not show any disclaimer."""
        patient = PatientFactory()
        conversation = AgentConversationFactory(patient=patient)
        msg = AgentMessageFactory(
            conversation=conversation,
            role="assistant",
            confidence_score=None,
        )

        html = self._render_bubble(msg)

        assert "let me involve a nurse" not in html
