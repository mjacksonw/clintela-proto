"""Tests for RAG-backed specialist agents."""

from unittest.mock import patch

import pytest

from apps.agents.specialists import (
    SPECIALIST_REGISTRY,
    CardiologySpecialist,
    NutritionSpecialist,
    PalliativeSpecialist,
    PharmacySpecialist,
    PTRehabSpecialist,
    RAGSpecialistAgent,
    SocialWorkSpecialist,
)


class TestSpecialistRegistry:
    def test_all_six_specialists_registered(self):
        assert len(SPECIALIST_REGISTRY) == 6
        expected = {
            "specialist_cardiology",
            "specialist_pharmacy",
            "specialist_nutrition",
            "specialist_pt_rehab",
            "specialist_social_work",
            "specialist_palliative",
        }
        assert set(SPECIALIST_REGISTRY.keys()) == expected

    def test_all_are_rag_specialist_subclasses(self):
        for cls in SPECIALIST_REGISTRY.values():
            assert issubclass(cls, RAGSpecialistAgent)


class TestSpecialistInit:
    def test_cardiology_agent_type(self):
        with patch("apps.agents.specialists.get_llm_client"):
            agent = CardiologySpecialist()
        assert agent.agent_type == "specialist_cardiology"
        assert agent.specialty_name == "Cardiology"

    def test_pharmacy_agent_type(self):
        with patch("apps.agents.specialists.get_llm_client"):
            agent = PharmacySpecialist()
        assert agent.agent_type == "specialist_pharmacy"
        assert agent.specialty_name == "Pharmacy"

    def test_nutrition_agent_type(self):
        with patch("apps.agents.specialists.get_llm_client"):
            agent = NutritionSpecialist()
        assert agent.agent_type == "specialist_nutrition"

    def test_pt_rehab_agent_type(self):
        with patch("apps.agents.specialists.get_llm_client"):
            agent = PTRehabSpecialist()
        assert agent.agent_type == "specialist_pt_rehab"
        assert agent.specialty_name == "Pt Rehab"

    def test_social_work_agent_type(self):
        with patch("apps.agents.specialists.get_llm_client"):
            agent = SocialWorkSpecialist()
        assert agent.agent_type == "specialist_social_work"

    def test_palliative_agent_type(self):
        with patch("apps.agents.specialists.get_llm_client"):
            agent = PalliativeSpecialist()
        assert agent.agent_type == "specialist_palliative"


class TestSpecialistSourceTypes:
    def test_cardiology_source_types(self):
        assert "acc_guideline" in CardiologySpecialist.SOURCE_TYPES
        assert "hospital_protocol" in CardiologySpecialist.SOURCE_TYPES

    def test_nutrition_source_types(self):
        assert "clinical_research" in NutritionSpecialist.SOURCE_TYPES
        assert "hospital_protocol" in NutritionSpecialist.SOURCE_TYPES

    def test_social_work_source_types(self):
        assert SocialWorkSpecialist.SOURCE_TYPES == ["hospital_protocol"]

    def test_palliative_has_all_source_types(self):
        assert len(PalliativeSpecialist.SOURCE_TYPES) == 3


class TestSpecialistProcess:
    @pytest.mark.asyncio
    async def test_process_with_rag_evidence(self):
        """Specialist returns confident response when RAG evidence is strong."""
        with patch("apps.agents.specialists.get_llm_client"):
            agent = CardiologySpecialist()

        agent._call_llm = _mock_llm_call("Based on the ACC CABG Recovery Guidelines, mild swelling is expected.")

        result = await agent.process(
            "Is swelling normal after surgery?",
            {
                "patient": {"name": "Test Patient", "surgery_type": "CABG", "days_post_op": 3},
                "rag_context": "<clinical_evidence>\nSwelling is normal post-CABG.\n</clinical_evidence>",
                "rag_top_similarity": 0.90,
            },
        )

        assert result.agent_type == "specialist_cardiology"
        assert "swelling" in result.response.lower()
        assert result.metadata["has_rag_evidence"] is True
        # High RAG similarity should boost confidence above escalation threshold
        assert result.confidence >= 0.70
        assert result.escalate is False

    @pytest.mark.asyncio
    async def test_process_without_rag_escalates_on_low_confidence(self):
        """Specialist escalates when confidence is low (short response, no RAG)."""
        with patch("apps.agents.specialists.get_llm_client"):
            agent = PharmacySpecialist()

        # Short response + truncated finish reason triggers low confidence
        async def mock_llm(*args, **kwargs):
            return {"content": "Unsure.", "finish_reason": "length"}

        agent._call_llm = mock_llm

        result = await agent.process(
            "Can I take ibuprofen?",
            {
                "patient": {"name": "Test"},
                "rag_context": "",
                "rag_top_similarity": 0.0,
            },
        )

        assert result.escalate is True
        assert result.metadata["has_rag_evidence"] is False

    @pytest.mark.asyncio
    async def test_process_llm_error_escalates(self):
        """LLM failure triggers escalation with care team language."""
        from apps.agents.llm_client import LLMError

        with patch("apps.agents.specialists.get_llm_client"):
            agent = NutritionSpecialist()

        async def fail(*args, **kwargs):
            raise LLMError("service unavailable")

        agent._call_llm = fail

        result = await agent.process(
            "What should I eat?",
            {"patient": {"name": "Test"}},
        )

        assert result.escalate is True
        assert "Nutrition" in result.response
        assert "LLM error" in result.escalation_reason

    @pytest.mark.asyncio
    async def test_all_specialists_process(self):
        """Verify all specialist types can process a message."""
        for agent_type, cls in SPECIALIST_REGISTRY.items():
            with patch("apps.agents.specialists.get_llm_client"):
                agent = cls()

            agent._call_llm = _mock_llm_call("Here is my guidance based on the clinical evidence.")

            result = await agent.process(
                "General question",
                {
                    "patient": {"name": "Test", "surgery_type": "CABG"},
                    "rag_context": "<clinical_evidence>\nEvidence\n</clinical_evidence>",
                    "rag_top_similarity": 0.85,
                },
            )

            assert result.agent_type == agent_type
            assert result.response


class TestGetAgentFactory:
    """Test that get_agent returns real specialists."""

    def test_get_specialist_returns_rag_agent(self):
        from apps.agents.agents import get_agent

        with patch("apps.agents.specialists.get_llm_client"):
            agent = get_agent("specialist_cardiology")
        assert isinstance(agent, CardiologySpecialist)
        assert isinstance(agent, RAGSpecialistAgent)

    def test_get_all_specialists(self):
        from apps.agents.agents import get_agent

        for agent_type in SPECIALIST_REGISTRY:
            with patch("apps.agents.specialists.get_llm_client"):
                agent = get_agent(agent_type)
            assert agent.agent_type == agent_type

    def test_get_unknown_raises(self):
        from apps.agents.agents import get_agent

        with pytest.raises(ValueError, match="Unknown agent type"):
            get_agent("specialist_unknown")


# --- helpers ---


def _mock_llm_call(content: str):
    """Return an async function that simulates an LLM response."""

    async def mock(*args, **kwargs):
        return {"content": content, "finish_reason": "stop"}

    return mock
