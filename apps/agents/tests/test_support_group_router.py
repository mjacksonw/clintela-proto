"""Tests for support group router, crisis detection, and orchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

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


# =========================================================================
# Orchestrator internal method tests (coverage boost)
# =========================================================================


class TestOrchestratorInternals:
    """Tests for SupportGroupOrchestrator helper methods."""

    @pytest.mark.asyncio
    async def test_handle_crisis_creates_escalation(self):
        """_handle_crisis creates message + escalation atomically."""
        from apps.agents.models import AgentMessage, Escalation

        @sync_to_async
        def _setup():
            patient = PatientFactory()
            conversation = AgentConversationFactory(
                patient=patient,
                conversation_type="support_group",
                generation_id=0,
            )
            return patient, conversation

        patient, conversation = await _setup()

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)

        result = await orchestrator._handle_crisis(patient, conversation, "I want to end it all", source="keyword")

        assert result["type"] == "crisis_detected"
        assert result["escalate"] is True
        assert result["source"] == "keyword"

        # Verify DB records created
        @sync_to_async
        def _verify():
            assert AgentMessage.objects.filter(conversation=conversation, content="I want to end it all").exists()
            esc = Escalation.objects.filter(patient=patient, conversation=conversation).first()
            assert esc is not None
            assert esc.severity == "critical"
            assert "keyword" in esc.reason
            assert "[TRIGGERING MESSAGE]" in esc.conversation_excerpt

        await _verify()

    @pytest.mark.asyncio
    async def test_build_patient_context_basic(self):
        """_build_patient_context returns name, procedure, days_post_op."""

        @sync_to_async
        def _setup():
            patient = PatientFactory()
            return patient

        patient = await _setup()

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)
        ctx = orchestrator._build_patient_context(patient)

        assert "name" in ctx
        assert "procedure" in ctx
        assert "days_post_op" in ctx

    @pytest.mark.asyncio
    async def test_get_conversation_history(self):
        """_get_conversation_history returns recent messages as dicts."""

        @sync_to_async
        def _setup():
            from apps.agents.tests.factories import AgentMessageFactory

            patient = PatientFactory()
            conv = AgentConversationFactory(
                patient=patient,
                conversation_type="support_group",
            )
            AgentMessageFactory(conversation=conv, role="user", content="Hello group")
            AgentMessageFactory(conversation=conv, role="assistant", content="Hi there!", persona_id="maria")
            return conv

        conv = await _setup()

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)
        history = await orchestrator._get_conversation_history(conv)

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello group"
        assert history[1]["persona_id"] == "maria"

    @pytest.mark.asyncio
    async def test_get_recent_messages_text(self):
        """_get_recent_messages_text returns formatted text."""

        @sync_to_async
        def _setup():
            from apps.agents.tests.factories import AgentMessageFactory

            patient = PatientFactory()
            conv = AgentConversationFactory(
                patient=patient,
                conversation_type="support_group",
            )
            AgentMessageFactory(conversation=conv, role="user", content="I feel tired")
            AgentMessageFactory(conversation=conv, role="assistant", content="That's normal", persona_id="maria")
            return conv

        conv = await _setup()

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)
        text = await orchestrator._get_recent_messages_text(conv, limit=5)

        assert "Patient: I feel tired" in text
        assert "maria: That's normal" in text

    @pytest.mark.asyncio
    async def test_generate_persona_response_happy(self):
        """_generate_persona_response returns LLM content."""
        from apps.agents.personas import get_persona

        persona = get_persona("maria")
        llm = _make_mock_llm(generate_return={"content": "Oh sweetheart, you're doing great!"})
        orchestrator = SupportGroupOrchestrator(llm_client=llm)

        response = await orchestrator._generate_persona_response(
            persona=persona,
            system_prompt="You are Maria.",
            patient_message="I walked today!",
            history=[
                {"role": "user", "content": "Hello", "persona_id": None},
                {"role": "assistant", "content": "Hi!", "persona_id": "maria"},
            ],
            plan_intent="celebrate progress",
        )

        assert response == "Oh sweetheart, you're doing great!"
        llm.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_persona_response_failure(self):
        """_generate_persona_response returns fallback on LLM error."""
        from apps.agents.personas import get_persona

        persona = get_persona("maria")
        llm = AsyncMock()
        llm.generate = AsyncMock(side_effect=Exception("LLM down"))
        orchestrator = SupportGroupOrchestrator(llm_client=llm)

        response = await orchestrator._generate_persona_response(
            persona=persona,
            system_prompt="You are Maria.",
            patient_message="Hello",
            history=[],
        )

        assert "gathering my thoughts" in response

    @pytest.mark.asyncio
    async def test_save_message(self):
        """_save_message persists an AgentMessage."""
        from apps.agents.models import AgentMessage

        @sync_to_async
        def _setup():
            patient = PatientFactory()
            conv = AgentConversationFactory(
                patient=patient,
                conversation_type="support_group",
                generation_id=1,
            )
            return conv

        conv = await _setup()

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)
        msg = await orchestrator._save_message(
            conversation=conv,
            role="assistant",
            content="Test response",
            persona_id="james",
            generation_id=1,
        )

        assert msg.persona_id == "james"
        assert msg.generation_id == 1

        @sync_to_async
        def _verify():
            assert AgentMessage.objects.filter(id=msg.id).exists()

        await _verify()

    @pytest.mark.asyncio
    async def test_schedule_followups(self):
        """_schedule_followups calls Celery delay for each followup."""
        from apps.agents.support_group import FollowupPlan

        @sync_to_async
        def _setup():
            patient = PatientFactory()
            conv = AgentConversationFactory(
                patient=patient,
                conversation_type="support_group",
                generation_id=1,
            )
            return conv

        conv = await _setup()

        plan = GroupResponsePlan(
            crisis_detected=False,
            patient_mood="neutral",
            primary_responder="maria",
            followups=[
                FollowupPlan(persona_id="james", delay=60, intent="share experience"),
                FollowupPlan(persona_id="tony", delay=90, intent="lighten mood"),
            ],
            reactions=[],
            silent=["linda", "robert", "diane", "priya"],
        )

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)

        with patch("apps.agents.tasks.deliver_support_group_followup") as mock_task:
            mock_task.delay = MagicMock()
            await orchestrator._schedule_followups(conv, plan, {"name": "Alice"})

        assert mock_task.delay.call_count == 2

    @pytest.mark.asyncio
    async def test_schedule_reactions(self):
        """_schedule_reactions calls Celery delay for each reaction."""
        from apps.agents.support_group import ReactionPlan

        @sync_to_async
        def _setup():
            from apps.agents.tests.factories import AgentMessageFactory

            patient = PatientFactory()
            conv = AgentConversationFactory(
                patient=patient,
                conversation_type="support_group",
                generation_id=1,
            )
            msg = AgentMessageFactory(conversation=conv, role="assistant", content="Hi!", persona_id="maria")
            return conv, msg

        conv, msg = await _setup()

        plan = GroupResponsePlan(
            crisis_detected=False,
            patient_mood="neutral",
            primary_responder="maria",
            followups=[],
            reactions=[
                ReactionPlan(persona_id="tony", emoji="thumbs_up", delay=20),
            ],
            silent=["james", "linda", "robert", "diane", "priya"],
        )

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)

        with patch("apps.agents.tasks.deliver_support_group_reaction") as mock_task:
            mock_task.delay = MagicMock()
            await orchestrator._schedule_reactions(msg, plan, conv.generation_id)

        assert mock_task.delay.call_count == 1

    @pytest.mark.asyncio
    async def test_process_message_router_crisis(self):
        """Router returning crisis_detected=True triggers escalation."""

        @sync_to_async
        def _setup():
            patient = PatientFactory()
            conversation = AgentConversationFactory(
                patient=patient,
                conversation_type="support_group",
                generation_id=0,
            )
            conversation.persona_memories = {}
            conversation.save()
            return patient, conversation

        patient, conversation = await _setup()

        crisis_plan = GroupResponsePlan(
            crisis_detected=True,
            patient_mood="distressed",
            primary_responder="maria",
            followups=[],
            reactions=[],
            silent=["james", "linda", "tony", "priya", "robert", "diane"],
        )

        llm = _make_mock_llm()
        orchestrator = SupportGroupOrchestrator(llm_client=llm)

        with (
            patch.object(
                orchestrator.router,
                "plan_group_response",
                new_callable=AsyncMock,
                return_value=crisis_plan,
            ),
            patch.object(
                orchestrator,
                "_handle_crisis",
                new_callable=AsyncMock,
                return_value={"type": "crisis_detected", "escalate": True, "source": "router"},
            ) as mock_crisis,
        ):
            result = await orchestrator.process_message(
                patient=patient,
                conversation=conversation,
                message="I feel hopeless",
            )

        assert result["escalate"] is True
        mock_crisis.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_router_crisis_recheck_returns_true(self):
        """_crisis_recheck returns True when LLM says crisis."""
        llm = AsyncMock()
        llm.generate_json = AsyncMock(return_value={"crisis": True})
        router = SupportGroupRouter(llm_client=llm)

        result = await router._crisis_recheck("I want to die")
        assert result is True

    @pytest.mark.asyncio
    async def test_router_crisis_recheck_failure(self):
        """_crisis_recheck returns False on LLM failure."""
        llm = AsyncMock()
        llm.generate_json = AsyncMock(side_effect=Exception("timeout"))
        router = SupportGroupRouter(llm_client=llm)

        result = await router._crisis_recheck("I want to die")
        assert result is False
