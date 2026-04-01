"""Tests for support group Celery tasks.

Covers: deliver_support_group_followup, deliver_support_group_reaction,
summarize_persona_memory, send_weekly_group_prompt, check_support_group_absence.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.utils import timezone

from apps.agents.models import AgentMessage, SupportGroupReaction
from apps.agents.tasks import (
    check_support_group_absence,
    deliver_support_group_followup,
    deliver_support_group_reaction,
    send_weekly_group_prompt,
    summarize_persona_memory,
)
from apps.agents.tests.factories import (
    AgentConversationFactory,
    AgentMessageFactory,
    PatientFactory,
)

pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_persona():
    """Return a minimal Persona-like object for mocking."""
    p = MagicMock()
    p.id = "maria"
    p.name = "Maria"
    p.avatar_color = "#8B5CF6"
    p.avatar_color_dark = "#A78BFA"
    p.avatar_initials = "MG"
    p.weekly_prompt = "How is everyone doing this week?"
    return p


def _sg_conversation(patient=None, **kwargs):
    """Create a support group conversation."""
    return AgentConversationFactory(
        patient=patient or PatientFactory(),
        conversation_type="support_group",
        **kwargs,
    )


def _noop_channel_layer():
    """Patch get_channel_layer to return None (skip WS push)."""
    return patch("channels.layers.get_channel_layer", return_value=None)


def _mock_llm(content="Mock response."):
    """Return a mock LLM client with async generate."""
    llm = MagicMock()
    llm.generate = AsyncMock(return_value={"content": content})
    return llm


# ==========================================================================
# deliver_support_group_followup
# ==========================================================================


@patch("apps.agents.personas.build_persona_prompt", return_value="system prompt")
@patch("apps.agents.personas.get_persona")
@patch("apps.agents.llm_client.get_llm_client")
def test_deliver_followup_happy_path(mock_get_llm, mock_get_persona, mock_build_prompt):
    """generation_id matches -> persona response delivered."""
    persona = _make_persona()
    mock_get_persona.return_value = persona
    mock_get_llm.return_value = _mock_llm("Take it easy today!")

    conv = _sg_conversation(generation_id=1)
    AgentMessageFactory(conversation=conv, role="user", content="I'm feeling tired")

    with _noop_channel_layer():
        result = deliver_support_group_followup(
            str(conv.id),
            "maria",
            "empathy",
            1,
            {"procedure_type": "cardiac_surgery_general"},
        )

    assert result["success"] is True
    assert result["persona_id"] == "maria"

    msg = AgentMessage.objects.filter(
        conversation=conv,
        persona_id="maria",
        generation_id=1,
    ).first()
    assert msg is not None
    assert msg.content == "Take it easy today!"


def test_deliver_followup_stale():
    """generation_id mismatch -> skip silently (no message created)."""
    conv = _sg_conversation(generation_id=5)

    result = deliver_support_group_followup(
        str(conv.id),
        "maria",
        "empathy",
        3,
        {},
    )

    assert result["skipped"] is True
    assert result["reason"] == "stale_generation"
    assert not AgentMessage.objects.filter(conversation=conv, persona_id="maria").exists()


def test_deliver_followup_conversation_deleted():
    """Conversation deleted -> log warning, skip."""
    result = deliver_support_group_followup(
        "00000000-0000-0000-0000-000000000000",
        "maria",
        "empathy",
        1,
        {},
    )

    assert result["skipped"] is True
    assert result["reason"] == "conversation_deleted"


# ==========================================================================
# deliver_support_group_reaction
# ==========================================================================


def test_deliver_reaction_happy_path():
    """Reaction created and matches generation_id."""
    conv = _sg_conversation(generation_id=2)
    msg = AgentMessageFactory(
        conversation=conv,
        role="user",
        content="I walked a mile today!",
    )

    with _noop_channel_layer():
        result = deliver_support_group_reaction(str(msg.id), "james", "💪", 2)

    assert result["success"] is True
    assert SupportGroupReaction.objects.filter(message=msg, persona_id="james").exists()


def test_deliver_reaction_stale():
    """generation_id mismatch -> skip."""
    conv = _sg_conversation(generation_id=5)
    msg = AgentMessageFactory(conversation=conv, role="user", content="hi")

    result = deliver_support_group_reaction(str(msg.id), "james", "💪", 2)

    assert result["skipped"] is True
    assert result["reason"] == "stale_generation"


def test_deliver_reaction_duplicate():
    """IntegrityError from duplicate reaction -> caught, ignored."""
    conv = _sg_conversation(generation_id=1)
    msg = AgentMessageFactory(conversation=conv, role="user", content="hi")

    with _noop_channel_layer():
        deliver_support_group_reaction(str(msg.id), "james", "💪", 1)

    with _noop_channel_layer():
        result = deliver_support_group_reaction(str(msg.id), "james", "❤️", 1)

    assert result["skipped"] is True
    assert result["reason"] == "duplicate"
    assert SupportGroupReaction.objects.filter(message=msg, persona_id="james").count() == 1


# ==========================================================================
# summarize_persona_memory
# ==========================================================================


@patch("apps.agents.llm_client.get_llm_client")
def test_summarize_persona_memory_happy_path(mock_get_llm):
    """Messages -> per-persona summaries updated."""
    mock_get_llm.return_value = _mock_llm("Patient is recovering well.")

    conv = _sg_conversation()
    for i in range(5):
        AgentMessageFactory(conversation=conv, role="user", content=f"msg {i}")
    for i in range(3):
        AgentMessageFactory(
            conversation=conv,
            role="assistant",
            content=f"maria reply {i}",
            persona_id="maria",
        )
    for i in range(2):
        AgentMessageFactory(
            conversation=conv,
            role="assistant",
            content=f"james reply {i}",
            persona_id="james",
        )

    james_persona = _make_persona()
    james_persona.id = "james"
    james_persona.name = "James"

    with patch("apps.agents.personas.PERSONA_REGISTRY", {"maria": _make_persona(), "james": james_persona}):
        result = summarize_persona_memory(str(conv.id))

    assert result["success"] is True
    assert "maria" in result["personas_updated"]
    assert "james" in result["personas_updated"]

    conv.refresh_from_db()
    assert "maria" in conv.persona_memories
    assert "james" in conv.persona_memories


# ==========================================================================
# send_weekly_group_prompt
# ==========================================================================


def test_weekly_prompt_engaged_patient():
    """Patient has sent messages -> prompt sent."""
    patient = PatientFactory()
    conv = _sg_conversation(patient=patient)
    AgentMessageFactory(conversation=conv, role="user", content="hello group")

    persona = _make_persona()
    registry = {"maria": persona}

    with patch("apps.agents.personas.PERSONA_REGISTRY", registry), _noop_channel_layer():
        result = send_weekly_group_prompt(str(patient.id))

    assert result["success"] is True
    assert AgentMessage.objects.filter(
        conversation=conv,
        metadata__weekly_prompt=True,
    ).exists()


def test_weekly_prompt_unengaged_patient():
    """No user messages -> skip."""
    patient = PatientFactory()
    _sg_conversation(patient=patient)

    result = send_weekly_group_prompt(str(patient.id))

    assert result["skipped"] is True
    assert result["reason"] == "not_engaged"


# ==========================================================================
# check_support_group_absence
# ==========================================================================


def test_absence_check_engaged_2_days():
    """2+ days silence -> Maria check-in sent."""
    patient = PatientFactory()
    conv = _sg_conversation(patient=patient)
    msg = AgentMessageFactory(conversation=conv, role="user", content="see you later")
    AgentMessage.objects.filter(id=msg.id).update(
        created_at=timezone.now() - timedelta(days=3),
    )

    persona = _make_persona()
    registry = {"maria": persona}

    with patch("apps.agents.personas.PERSONA_REGISTRY", registry), _noop_channel_layer():
        result = check_support_group_absence(str(patient.id))

    assert result["success"] is True
    assert result["days_absent"] >= 2

    checkin_msg = AgentMessage.objects.filter(
        conversation=conv,
        persona_id="maria",
        metadata__absence_checkin=True,
    ).first()
    assert checkin_msg is not None
    assert patient.user.first_name in checkin_msg.content


def test_absence_check_recent_activity():
    """Recent message -> skip."""
    patient = PatientFactory()
    conv = _sg_conversation(patient=patient)
    AgentMessageFactory(conversation=conv, role="user", content="just checking in")

    result = check_support_group_absence(str(patient.id))

    assert result["skipped"] is True
    assert result["reason"] == "recent_activity"


def test_absence_check_unengaged():
    """Never sent a message -> skip (engagement gate)."""
    patient = PatientFactory()
    _sg_conversation(patient=patient)

    result = check_support_group_absence(str(patient.id))

    assert result["skipped"] is True
    assert result["reason"] == "not_engaged"
