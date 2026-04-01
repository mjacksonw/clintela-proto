"""Tests for support group model changes — conversation types, personas, reactions, escalations."""

import pytest
from django.db import IntegrityError

from apps.agents.services import ConversationService
from apps.agents.tests.factories import (
    AgentConversationFactory,
    AgentMessageFactory,
    EscalationFactory,
    PatientFactory,
    SupportGroupReactionFactory,
)

pytestmark = pytest.mark.django_db


class TestConversationType:
    def test_conversation_type_default(self):
        """New conversation defaults to 'care_team'."""
        conv = AgentConversationFactory()
        assert conv.conversation_type == "care_team"

    def test_conversation_type_support_group(self):
        """Can create with 'support_group'."""
        conv = AgentConversationFactory(conversation_type="support_group")
        assert conv.conversation_type == "support_group"

    def test_get_or_create_isolates_by_type(self):
        """Care team and support group conversations don't cross."""
        patient = PatientFactory()

        care_conv = ConversationService.get_or_create_conversation(
            patient=patient,
            agent_type="supervisor",
            conversation_type="care_team",
        )
        sg_conv = ConversationService.get_or_create_conversation(
            patient=patient,
            agent_type="supervisor",
            conversation_type="support_group",
        )

        assert care_conv.pk != sg_conv.pk
        assert care_conv.conversation_type == "care_team"
        assert sg_conv.conversation_type == "support_group"

        # Re-fetching returns the same conversations, not new ones
        care_conv_2 = ConversationService.get_or_create_conversation(
            patient=patient,
            agent_type="supervisor",
            conversation_type="care_team",
        )
        sg_conv_2 = ConversationService.get_or_create_conversation(
            patient=patient,
            agent_type="supervisor",
            conversation_type="support_group",
        )
        assert care_conv_2.pk == care_conv.pk
        assert sg_conv_2.pk == sg_conv.pk


class TestGenerationAndMemory:
    def test_generation_id_default(self):
        """New conversation starts at 0."""
        conv = AgentConversationFactory()
        assert conv.generation_id == 0

    def test_persona_memories_default(self):
        """New conversation has empty dict for persona_memories."""
        conv = AgentConversationFactory()
        assert conv.persona_memories == {}


class TestPersonaMessages:
    def test_persona_id_null_for_care_team(self):
        """Care team messages have null persona_id."""
        msg = AgentMessageFactory()
        assert msg.persona_id is None

    def test_persona_id_set_for_support_group(self):
        """Support group messages have persona_id."""
        conv = AgentConversationFactory(conversation_type="support_group")
        msg = AgentMessageFactory(
            conversation=conv,
            role="assistant",
            persona_id="maria",
        )
        assert msg.persona_id == "maria"


class TestSupportGroupReaction:
    def test_reaction_unique_constraint(self):
        """Same persona can't react twice to same message."""
        msg = AgentMessageFactory()
        SupportGroupReactionFactory(message=msg, persona_id="maria")

        with pytest.raises(IntegrityError):
            SupportGroupReactionFactory(message=msg, persona_id="maria")

    def test_reaction_different_personas(self):
        """Different personas can react to same message."""
        msg = AgentMessageFactory()
        r1 = SupportGroupReactionFactory(message=msg, persona_id="maria")
        r2 = SupportGroupReactionFactory(message=msg, persona_id="james")

        assert r1.pk != r2.pk
        assert msg.reactions.count() == 2


class TestEscalationExcerpt:
    def test_escalation_conversation_excerpt(self):
        """SG crisis stores excerpt in conversation_excerpt TextField."""
        conv = AgentConversationFactory(conversation_type="support_group")
        escalation = EscalationFactory(
            conversation=conv,
            conversation_excerpt="Patient: I can't take this anymore\nMaria: I hear you.",
        )
        escalation.refresh_from_db()
        assert "I can't take this anymore" in escalation.conversation_excerpt

    def test_escalation_conversation_excerpt_blank(self):
        """Non-SG escalation has blank excerpt."""
        escalation = EscalationFactory()
        assert escalation.conversation_excerpt == ""
