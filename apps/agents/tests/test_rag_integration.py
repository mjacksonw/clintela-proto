"""Tests for RAG integration in agent workflow."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from apps.agents.agents import calculate_confidence_score
from apps.agents.prompts import (
    build_care_coordinator_prompt,
    build_nurse_triage_prompt,
    build_specialist_prompt,
)
from apps.agents.workflow import AgentWorkflow
from apps.knowledge.retrieval import EMPTY_RAG_RESULT, RAGResult, RetrievalResult


class TestConfidenceScoreWithRAG:
    """Test confidence scoring adjustments from RAG results."""

    def test_strong_rag_boosts_confidence(self):
        score = calculate_confidence_score(
            response="Normal recovery guidance.",
            agent_type="care_coordinator",
            rag_top_similarity=0.90,
        )
        # Base 0.85 + 0.10 RAG bonus = 0.95
        assert score == pytest.approx(0.95, abs=0.01)

    def test_moderate_rag_small_boost(self):
        score = calculate_confidence_score(
            response="Normal recovery guidance.",
            agent_type="care_coordinator",
            rag_top_similarity=0.75,
        )
        # Base 0.85 + 0.05 RAG bonus = 0.90
        assert score == pytest.approx(0.90, abs=0.01)

    def test_no_rag_results_penalty(self):
        score = calculate_confidence_score(
            response="Normal recovery guidance.",
            agent_type="care_coordinator",
            rag_top_similarity=0.0,
        )
        # Base 0.85 - 0.05 penalty = 0.80
        assert score == pytest.approx(0.80, abs=0.01)

    def test_rag_none_no_effect(self):
        """When RAG is disabled (None), no adjustment."""
        score_without = calculate_confidence_score(
            response="Normal recovery guidance.",
            agent_type="care_coordinator",
            rag_top_similarity=None,
        )
        score_base = calculate_confidence_score(
            response="Normal recovery guidance.",
            agent_type="care_coordinator",
        )
        assert score_without == score_base

    def test_rag_with_critical_keywords_still_low(self):
        """RAG bonus doesn't override critical keyword penalty."""
        score = calculate_confidence_score(
            response="Pain assessment requires immediate clinical review for the patient.",
            agent_type="nurse_triage",
            has_critical_keywords=True,
            rag_top_similarity=0.90,
        )
        # Base 0.85 - 0.30 (critical) + 0.10 (RAG) - 0.05 (nurse) = 0.60
        assert score == pytest.approx(0.60, abs=0.01)

    def test_confidence_capped_at_1(self):
        score = calculate_confidence_score(
            response="Normal recovery guidance.",
            agent_type="care_coordinator",
            llm_finish_reason="stop",
            rag_top_similarity=0.95,
        )
        assert score <= 1.0


class TestPromptRAGContext:
    """Test that prompts correctly include RAG context."""

    def test_care_coordinator_prompt_includes_rag(self):
        rag_context = "<clinical_evidence>\nTest evidence\n</clinical_evidence>"
        prompt = build_care_coordinator_prompt(
            patient_context="Name: Test",
            conversation_history="",
            message="How is my recovery?",
            rag_context=rag_context,
        )
        assert "<clinical_evidence>" in prompt
        assert "Test evidence" in prompt

    def test_care_coordinator_prompt_empty_rag(self):
        prompt = build_care_coordinator_prompt(
            patient_context="Name: Test",
            conversation_history="",
            message="How is my recovery?",
            rag_context="",
        )
        assert "<clinical_evidence>" not in prompt

    def test_nurse_triage_prompt_includes_rag(self):
        rag_context = "<clinical_evidence>\nClinical guideline text\n</clinical_evidence>"
        prompt = build_nurse_triage_prompt(
            surgery_type="CABG",
            surgery_date="2024-01-01",
            days_post_op=5,
            current_phase="early",
            medications=["metoprolol"],
            allergies=[],
            pathway_context="{}",
            message="I have swelling",
            rag_context=rag_context,
        )
        assert "<clinical_evidence>" in prompt
        assert "Clinical guideline text" in prompt

    def test_specialist_prompt_includes_rag(self):
        rag_context = "<clinical_evidence>\nCardiac guideline\n</clinical_evidence>"
        prompt = build_specialist_prompt(
            agent_type="specialist_cardiology",
            patient_context="Name: Test Patient",
            message="Can I exercise?",
            rag_context=rag_context,
        )
        assert "<clinical_evidence>" in prompt
        assert "Cardiac guideline" in prompt
        assert "Cardiology Specialist" in prompt

    def test_specialist_prompt_all_types(self):
        """All specialist types have custom instructions."""
        from apps.agents.prompts import SPECIALIST_INSTRUCTIONS

        for agent_type, instructions in SPECIALIST_INSTRUCTIONS.items():
            prompt = build_specialist_prompt(
                agent_type=agent_type,
                patient_context="Name: Test",
                message="Question",
            )
            # Each should contain its specialty-specific text
            assert instructions[:30] in prompt

    def test_specialist_prompt_unknown_type_fallback(self):
        prompt = build_specialist_prompt(
            agent_type="specialist_unknown",
            patient_context="Name: Test",
            message="Question",
        )
        assert "specialist_unknown" in prompt


class TestWorkflowRAGHelpers:
    """Test the _retrieve_clinical_evidence and _store_citations helpers."""

    @pytest.fixture
    def workflow(self):
        with patch("apps.agents.workflow.get_llm_client"):
            wf = AgentWorkflow()
            return wf

    @pytest.mark.asyncio
    async def test_retrieve_returns_empty_when_rag_disabled(self, workflow):
        workflow._rag_enabled = False
        result = await workflow._retrieve_clinical_evidence("test", {})
        assert result is EMPTY_RAG_RESULT

    @pytest.mark.asyncio
    async def test_retrieve_returns_empty_on_error(self, workflow):
        workflow._rag_enabled = True
        with patch(
            "apps.knowledge.retrieval.KnowledgeRetrievalService.search_and_format",
            side_effect=Exception("boom"),
        ):
            result = await workflow._retrieve_clinical_evidence("test", {})
            assert result is EMPTY_RAG_RESULT

    @pytest.mark.asyncio
    async def test_retrieve_calls_service_when_enabled(self, workflow):
        workflow._rag_enabled = True
        mock_rag = RAGResult(
            context_str="<clinical_evidence>test</clinical_evidence>",
            citations=[],
            top_similarity=0.85,
        )
        with patch(
            "apps.knowledge.retrieval.KnowledgeRetrievalService.search_and_format",
            new_callable=AsyncMock,
            return_value=mock_rag,
        ):
            result = await workflow._retrieve_clinical_evidence(
                "swelling question",
                {"patient": {"hospital_id": uuid.uuid4(), "id": uuid.uuid4()}},
            )
            assert result.top_similarity == 0.85

    @pytest.mark.asyncio
    async def test_store_citations_skips_when_no_results(self, workflow):
        """No-op when RAG result is empty."""
        await workflow._store_citations(
            agent_message_id=uuid.uuid4(),
            rag_result=EMPTY_RAG_RESULT,
        )
        # Should not raise

    @pytest.mark.asyncio
    async def test_store_citations_skips_when_no_message_id(self, workflow):
        """No-op when agent_message_id is None."""
        rag = RAGResult(
            context_str="test",
            citations=[
                RetrievalResult(
                    document_id=uuid.uuid4(),
                    content="test",
                    title="test",
                    similarity_score=0.9,
                    text_rank_score=0.1,
                    combined_score=0.8,
                    source_name="ACC",
                    source_type="acc_guideline",
                )
            ],
            top_similarity=0.9,
        )
        await workflow._store_citations(agent_message_id=None, rag_result=rag)
        # Should not raise

    @pytest.mark.asyncio
    async def test_store_citations_updates_metadata(self, workflow):
        rag = RAGResult(
            context_str="test",
            citations=[
                RetrievalResult(
                    document_id=uuid.uuid4(),
                    content="test",
                    title="test",
                    similarity_score=0.9,
                    text_rank_score=0.1,
                    combined_score=0.85,
                    source_name="ACC",
                    source_type="acc_guideline",
                )
            ],
            top_similarity=0.9,
        )
        metadata = {}
        with patch(
            "apps.agents.models.MessageCitation.objects.bulk_create",
            return_value=[],
        ):
            await workflow._store_citations(
                agent_message_id=uuid.uuid4(),
                rag_result=rag,
                metadata=metadata,
            )
        assert metadata["rag_result_count"] == 1
        assert metadata["rag_top_similarity"] == 0.9


@pytest.mark.django_db
class TestWorkflowRAGIntegration:
    """Integration tests for RAG in the full workflow."""

    @pytest.mark.asyncio
    async def test_care_coordinator_node_with_rag_disabled(self):
        """Care coordinator works normally when RAG is disabled."""
        from apps.agents.agents import AgentResult

        with patch("apps.agents.workflow.get_llm_client"):
            workflow = AgentWorkflow()
            workflow._rag_enabled = False

        mock_agent_result = AgentResult(
            response="I'm here to help.",
            agent_type="care_coordinator",
            confidence=0.85,
            escalate=False,
            escalation_reason="",
            metadata={},
        )

        async def mock_process(message, context):
            return mock_agent_result

        workflow.care_coordinator.process = mock_process

        state = {
            "message": "How is my recovery going?",
            "context": {"patient": {"name": "Test"}},
            "routing": {},
            "result": {},
            "should_escalate": False,
            "escalation_reason": "",
        }

        result = await workflow._care_coordinator_node(state)
        assert result["result"]["response"] == "I'm here to help."
        assert result["result"]["rag_result"] is EMPTY_RAG_RESULT
