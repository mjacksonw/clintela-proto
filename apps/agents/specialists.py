"""RAG-backed specialist agent implementations.

Each specialist uses clinical knowledge retrieval to answer
domain-specific questions, only escalating when evidence is
insufficient or the question requires human clinical judgment.
"""

import logging
from typing import Any

from apps.agents.agents import CONFIDENCE_ESCALATION_THRESHOLD, AgentResult, BaseAgent, calculate_confidence_score
from apps.agents.llm_client import LLMClient, LLMError
from apps.agents.prompts import build_specialist_prompt

logger = logging.getLogger(__name__)


class RAGSpecialistAgent(BaseAgent):
    """Base class for RAG-backed specialist agents.

    Handles RAG retrieval, prompt building with evidence context,
    citation tracking, and confidence scoring. Each specialty subclass
    provides its own domain-specific behavior via SPECIALIST_INSTRUCTIONS.
    """

    # Source types to prioritize for this specialist (subclasses can override)
    SOURCE_TYPES: list[str] = ["acc_guideline", "clinical_research", "hospital_protocol"]

    def __init__(self, agent_type: str, llm_client: LLMClient | None = None):
        super().__init__(agent_type, llm_client)
        self.specialty_name = agent_type.replace("specialist_", "").replace("_", " ").title()

    async def process(
        self,
        message: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Process message with specialist knowledge.

        The workflow injects rag_context and rag_top_similarity into context
        before calling this method.
        """
        patient = context.get("patient", {})
        rag_context = context.get("rag_context", "")
        rag_top_similarity = context.get("rag_top_similarity")

        patient_context = (
            f"Name: {patient.get('name', 'Patient')}\n"
            f"Surgery: {patient.get('surgery_type', 'Unknown')} "
            f"({patient.get('days_post_op', 0)} days ago)\n"
            f"Status: {patient.get('status', 'unknown')}"
        )

        prompt = build_specialist_prompt(
            agent_type=self.agent_type,
            patient_context=patient_context,
            message=message,
            rag_context=rag_context,
        )

        messages = self._build_messages(
            system_prompt=f"You are the {self.specialty_name} specialist for Clintela.",
            user_message=prompt,
        )

        try:
            response = await self._call_llm(messages, temperature=0.6)
            content = response.get("content", "")

            confidence = calculate_confidence_score(
                response=content,
                agent_type=self.agent_type,
                llm_finish_reason=response.get("finish_reason"),
                rag_top_similarity=rag_top_similarity,
            )

            # Escalate if confidence is low or no RAG evidence
            should_escalate = confidence < CONFIDENCE_ESCALATION_THRESHOLD

            return AgentResult(
                response=content,
                agent_type=self.agent_type,
                confidence=confidence,
                metadata={
                    "specialty": self.specialty_name,
                    "confidence_score": confidence,
                    "has_rag_evidence": bool(rag_context),
                },
                escalate=should_escalate,
                escalation_reason=(
                    f"Low confidence ({confidence:.2f}) for {self.specialty_name}" if should_escalate else ""
                ),
            )

        except LLMError as e:
            logger.error("Specialist %s failed: %s", self.agent_type, e)
            return AgentResult(
                response=(
                    f"I want to make sure you get the best guidance on this "
                    f"— let me involve our {self.specialty_name} team."
                ),
                agent_type=self.agent_type,
                escalate=True,
                escalation_reason=f"LLM error: {e}",
            )


class CardiologySpecialist(RAGSpecialistAgent):
    """Cardiac recovery, medications, activity restrictions."""

    SOURCE_TYPES = ["acc_guideline", "hospital_protocol"]

    def __init__(self, llm_client: LLMClient | None = None):
        super().__init__("specialist_cardiology", llm_client)


class PharmacySpecialist(RAGSpecialistAgent):
    """Medication questions, side effects, interactions.

    Never prescribes — explains what to discuss with the prescriber.
    """

    SOURCE_TYPES = ["acc_guideline", "hospital_protocol"]

    def __init__(self, llm_client: LLMClient | None = None):
        super().__init__("specialist_pharmacy", llm_client)


class NutritionSpecialist(RAGSpecialistAgent):
    """Dietary guidance, restrictions, hydration."""

    SOURCE_TYPES = ["clinical_research", "hospital_protocol"]

    def __init__(self, llm_client: LLMClient | None = None):
        super().__init__("specialist_nutrition", llm_client)


class PTRehabSpecialist(RAGSpecialistAgent):
    """Exercise, mobility, activity levels."""

    SOURCE_TYPES = ["clinical_research", "hospital_protocol"]

    def __init__(self, llm_client: LLMClient | None = None):
        super().__init__("specialist_pt_rehab", llm_client)


class SocialWorkSpecialist(RAGSpecialistAgent):
    """Insurance, transport, home care, emotional support."""

    SOURCE_TYPES = ["hospital_protocol"]

    def __init__(self, llm_client: LLMClient | None = None):
        super().__init__("specialist_social_work", llm_client)


class PalliativeSpecialist(RAGSpecialistAgent):
    """Pain management education, comfort, quality of life.

    Conservative — escalates readily when symptoms are concerning.
    """

    SOURCE_TYPES = ["acc_guideline", "clinical_research", "hospital_protocol"]

    def __init__(self, llm_client: LLMClient | None = None):
        super().__init__("specialist_palliative", llm_client)


# Registry for easy lookup
SPECIALIST_REGISTRY: dict[str, type[RAGSpecialistAgent]] = {
    "specialist_cardiology": CardiologySpecialist,
    "specialist_pharmacy": PharmacySpecialist,
    "specialist_nutrition": NutritionSpecialist,
    "specialist_pt_rehab": PTRehabSpecialist,
    "specialist_social_work": SocialWorkSpecialist,
    "specialist_palliative": PalliativeSpecialist,
}
