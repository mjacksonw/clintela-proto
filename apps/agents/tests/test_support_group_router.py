"""Tests for support group router, crisis detection, and orchestrator."""

from unittest.mock import AsyncMock, patch

import pytest
from asgiref.sync import sync_to_async
from pydantic import ValidationError

from apps.agents.constants import CRITICAL_KEYWORDS, SUPPORT_GROUP_DISTRESS_KEYWORDS
from apps.agents.personas import (
    PERSONA_REGISTRY,
    PROCEDURE_BACKSTORIES,
    get_procedure_backstory,
)
from apps.agents.support_group import (
    GroupResponsePlan,
    SupportGroupOrchestrator,
    SupportGroupRouter,
    detect_crisis_keywords,
)
from apps.agents.tests.factories import (
    AgentConversationFactory,
    PatientFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PLAN_DICT = {
    "crisis_detected": False,
    "patient_mood": "neutral",
    "primary_responder": "maria",
    "followups": [
        {"persona_id": "james", "delay": 60, "intent": "share similar experience"},
    ],
    "reactions": [
        {"persona_id": "tony", "emoji": "thumbs_up", "delay": 20},
    ],
    "silent": ["linda", "robert", "diane", "priya"],
}


def _make_mock_llm(**overrides):
    """Return a mock LLM client whose generate_json returns VALID_PLAN_DICT."""
    llm = AsyncMock()
    llm.generate_json = AsyncMock(return_value=overrides.get("json_return", VALID_PLAN_DICT))
    llm.generate = AsyncMock(return_value=overrides.get("generate_return", {"content": "I hear you, sweetheart."}))
    return llm


# =========================================================================
# Router tests
# =========================================================================


class TestSupportGroupRouter:
    """Tests for SupportGroupRouter.plan_group_response."""

    @pytest.mark.asyncio
    async def test_router_happy_path(self):
        """Valid message returns a GroupResponsePlan with valid persona IDs."""
        llm = _make_mock_llm()
        router = SupportGroupRouter(llm_client=llm)

        plan = await router.plan_group_response(
            message="I walked 10 minutes today!",
            patient_context={"name": "Alice", "procedure": "cabg", "days_post_op": 5},
            conversation_history=[],
        )

        assert isinstance(plan, GroupResponsePlan)
        assert plan.primary_responder in PERSONA_REGISTRY
        assert plan.crisis_detected is False
        assert plan.patient_mood == "neutral"
        for f in plan.followups:
            assert f.persona_id in PERSONA_REGISTRY
        for r in plan.reactions:
            assert r.persona_id in PERSONA_REGISTRY

    @pytest.mark.asyncio
    async def test_router_malformed_json(self):
        """LLM returning garbage triggers Maria fallback."""
        llm = AsyncMock()
        # First call: router itself gets garbage and raises
        llm.generate_json = AsyncMock(
            side_effect=[
                ValueError("not valid JSON"),
                # Second call: crisis recheck returns no crisis
                {"crisis": False},
            ]
        )
        router = SupportGroupRouter(llm_client=llm)

        plan = await router.plan_group_response(
            message="Feeling okay today.",
            patient_context={"name": "Alice", "procedure": "cabg", "days_post_op": 5},
            conversation_history=[],
        )

        assert plan.primary_responder == "maria"
        assert plan.followups == []
        assert plan.reactions == []

    @pytest.mark.asyncio
    async def test_router_invalid_persona_id(self):
        """Unknown persona_id in LLM response triggers fallback (Pydantic rejects it)."""
        bad_plan = {**VALID_PLAN_DICT, "primary_responder": "nonexistent_persona"}
        llm = AsyncMock()
        llm.generate_json = AsyncMock(
            side_effect=[
                bad_plan,  # Router call returns invalid persona
                {"crisis": False},  # Crisis recheck
            ]
        )
        router = SupportGroupRouter(llm_client=llm)

        plan = await router.plan_group_response(
            message="Hello everyone.",
            patient_context={"name": "Alice", "procedure": "cabg", "days_post_op": 5},
            conversation_history=[],
        )

        # Should have fallen back to Maria because Pydantic validation fails
        assert plan.primary_responder == "maria"

    @pytest.mark.asyncio
    async def test_router_llm_timeout(self):
        """Timeout from LLM triggers Maria fallback after retry."""
        llm = AsyncMock()
        llm.generate_json = AsyncMock(
            side_effect=[
                TimeoutError("LLM timed out"),
                {"crisis": False},  # Crisis recheck
            ]
        )
        router = SupportGroupRouter(llm_client=llm)

        plan = await router.plan_group_response(
            message="How is everyone?",
            patient_context={"name": "Alice", "procedure": "cabg", "days_post_op": 5},
            conversation_history=[],
        )

        assert plan.primary_responder == "maria"
        assert plan.followups == []

    @pytest.mark.asyncio
    async def test_router_crisis_detected(self):
        """Crisis message results in crisis_detected=True in plan."""
        crisis_plan = {**VALID_PLAN_DICT, "crisis_detected": True, "patient_mood": "distressed"}
        llm = _make_mock_llm(json_return=crisis_plan)
        router = SupportGroupRouter(llm_client=llm)

        plan = await router.plan_group_response(
            message="I want to end my life.",
            patient_context={"name": "Alice", "procedure": "cabg", "days_post_op": 5},
            conversation_history=[],
        )

        assert plan.crisis_detected is True

    @pytest.mark.asyncio
    async def test_router_mood_detection(self):
        """Struggling message yields patient_mood='struggling' in plan."""
        mood_plan = {**VALID_PLAN_DICT, "patient_mood": "struggling"}
        llm = _make_mock_llm(json_return=mood_plan)
        router = SupportGroupRouter(llm_client=llm)

        plan = await router.plan_group_response(
            message="I'm really struggling today, nothing feels right.",
            patient_context={"name": "Alice", "procedure": "cabg", "days_post_op": 5},
            conversation_history=[],
        )

        assert plan.patient_mood == "struggling"


# =========================================================================
# Crisis keyword detection tests
# =========================================================================


class TestDetectCrisisKeywords:
    """Tests for detect_crisis_keywords pre-LLM scan."""

    def test_detect_crisis_keywords_critical(self):
        """CRITICAL_KEYWORDS in message returns True."""
        for keyword in CRITICAL_KEYWORDS[:5]:
            assert detect_crisis_keywords(f"I have {keyword} right now") is True

    def test_detect_crisis_keywords_distress(self):
        """SUPPORT_GROUP_DISTRESS_KEYWORDS in message returns True."""
        for keyword in SUPPORT_GROUP_DISTRESS_KEYWORDS[:5]:
            assert detect_crisis_keywords(keyword) is True

    def test_detect_crisis_keywords_normal(self):
        """Normal message returns False."""
        assert detect_crisis_keywords("I walked 10 minutes today!") is False
        assert detect_crisis_keywords("Feeling good, thanks everyone.") is False
        assert detect_crisis_keywords("What's for dinner tonight?") is False


# =========================================================================
# GroupResponsePlan validation tests
# =========================================================================


class TestGroupResponsePlanValidation:
    """Tests for Pydantic validation on GroupResponsePlan."""

    def test_group_response_plan_validation(self):
        """Pydantic rejects invalid fields."""
        # Invalid patient_mood
        with pytest.raises(ValidationError):
            GroupResponsePlan(
                crisis_detected=False,
                patient_mood="INVALID_MOOD",
                primary_responder="maria",
                followups=[],
                reactions=[],
                silent=[],
            )

        # Missing required field (primary_responder)
        with pytest.raises(ValidationError):
            GroupResponsePlan(
                crisis_detected=False,
                patient_mood="neutral",
                followups=[],
                reactions=[],
                silent=[],
            )

    def test_group_response_plan_persona_validation(self):
        """Persona ID not in registry triggers ValidationError."""
        with pytest.raises(ValidationError, match="Unknown primary_responder"):
            GroupResponsePlan(
                crisis_detected=False,
                patient_mood="neutral",
                primary_responder="nonexistent_persona",
                followups=[],
                reactions=[],
                silent=[],
            )

        # Also fails for followup persona_id
        with pytest.raises(ValidationError, match="Unknown persona_id"):
            GroupResponsePlan(
                crisis_detected=False,
                patient_mood="neutral",
                primary_responder="maria",
                followups=[
                    {"persona_id": "fake_persona", "delay": 60, "intent": "test"},
                ],
                reactions=[],
                silent=[],
            )

        # Also fails for reaction persona_id
        with pytest.raises(ValidationError, match="Unknown persona_id"):
            GroupResponsePlan(
                crisis_detected=False,
                patient_mood="neutral",
                primary_responder="maria",
                followups=[],
                reactions=[
                    {"persona_id": "fake_persona", "emoji": "heart", "delay": 20},
                ],
                silent=[],
            )


# =========================================================================
# Orchestrator tests
# =========================================================================


class TestSupportGroupOrchestrator:
    """Tests for SupportGroupOrchestrator.process_message."""

    @pytest.mark.asyncio
    async def test_process_message_happy_path(self):
        """Full flow: crisis scan -> router -> primary -> schedule."""

        @sync_to_async
        def _setup():
            patient = PatientFactory()
            conversation = AgentConversationFactory(
                patient=patient,
                agent_type="supervisor",
                context={"conversation_type": "support_group"},
            )
            conversation.persona_memories = {}
            conversation.generation_id = 0
            conversation.save()
            return patient, conversation

        patient, conversation = await _setup()

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)

        with (
            patch(
                "apps.agents.support_group.SupportGroupOrchestrator._schedule_followups",
                new_callable=AsyncMock,
            ) as mock_followups,
            patch(
                "apps.agents.support_group.SupportGroupOrchestrator._schedule_reactions",
                new_callable=AsyncMock,
            ) as mock_reactions,
        ):
            result = await orchestrator.process_message(
                patient=patient,
                conversation=conversation,
                message="I walked 10 minutes today!",
            )

        assert result["type"] == "support_group_message"
        assert result["persona_id"] == "maria"
        assert result["escalate"] is False
        assert "content" in result
        mock_followups.assert_awaited_once()
        mock_reactions.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_message_crisis_keyword(self):
        """CRITICAL_KEYWORDS triggers escalation before LLM call."""

        @sync_to_async
        def _setup():
            patient = PatientFactory()
            conversation = AgentConversationFactory(
                patient=patient,
                agent_type="supervisor",
                context={"conversation_type": "support_group"},
            )
            conversation.persona_memories = {}
            conversation.generation_id = 0
            conversation.save()
            return patient, conversation

        patient, conversation = await _setup()

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)

        with patch(
            "apps.agents.support_group.SupportGroupOrchestrator._handle_crisis",
            new_callable=AsyncMock,
            return_value={"type": "crisis_detected", "escalate": True, "source": "keyword"},
        ) as mock_crisis:
            result = await orchestrator.process_message(
                patient=patient,
                conversation=conversation,
                message="I am having severe pain and chest pain",
            )

        assert result["type"] == "crisis_detected"
        assert result["escalate"] is True
        mock_crisis.assert_awaited_once()
        # LLM router should NOT have been called
        llm.generate_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_generation_id_increment(self):
        """F() increment + refresh_from_db returns correct int."""

        @sync_to_async
        def _setup():
            patient = PatientFactory()
            conversation = AgentConversationFactory(
                patient=patient,
                agent_type="supervisor",
            )
            conversation.generation_id = 5
            conversation.persona_memories = {}
            conversation.save()
            return patient, conversation

        _patient, conversation = await _setup()

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)

        initial_gen = conversation.generation_id
        await orchestrator._increment_generation_id(conversation)
        assert conversation.generation_id == initial_gen + 1

        # Increment again to make sure it keeps working
        await orchestrator._increment_generation_id(conversation)
        assert conversation.generation_id == initial_gen + 2

    def test_procedure_backstory_matching(self):
        """Patient procedure type maps to correct backstory variant."""
        # CABG procedure should use the cabg backstory map
        backstory = get_procedure_backstory("cabg", "james")
        assert backstory == PROCEDURE_BACKSTORIES["cabg"]["james"]
        assert backstory == "triple bypass"

        # Valve replacement for maria
        backstory = get_procedure_backstory("valve_replacement", "maria")
        assert backstory == "mitral valve repair"

        # Stent placement for linda
        backstory = get_procedure_backstory("stent_placement", "linda")
        assert backstory == "stent placement"

    def test_procedure_backstory_fallback(self):
        """Unknown procedure type falls back to cardiac_surgery_general."""
        backstory = get_procedure_backstory("totally_unknown_procedure", "maria")
        assert backstory == PROCEDURE_BACKSTORIES["cardiac_surgery_general"]["maria"]
        assert backstory == "open-heart surgery"

        backstory = get_procedure_backstory("totally_unknown_procedure", "james")
        assert backstory == "major heart surgery"

        # Also verify a persona_id not in the fallback map returns default
        backstory = get_procedure_backstory("totally_unknown_procedure", "nonexistent")
        assert backstory == "heart surgery"  # default from .get(..., "heart surgery")
