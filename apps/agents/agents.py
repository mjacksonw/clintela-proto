"""Core agent implementations for the multi-agent system."""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from apps.agents.llm_client import LLMClient, LLMError, get_llm_client
from apps.agents.prompts import (
    build_care_coordinator_prompt,
    build_documentation_prompt,
    build_nurse_triage_prompt,
    build_placeholder_specialist_prompt,
    build_supervisor_prompt,
)

logger = logging.getLogger(__name__)


class AgentResult:
    """Result from an agent invocation."""

    def __init__(
        self,
        response: str,
        agent_type: str,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
        escalate: bool = False,
        escalation_reason: str = "",
    ):
        self.response = response
        self.agent_type = agent_type
        self.confidence = confidence
        self.metadata = metadata or {}
        self.escalate = escalate
        self.escalation_reason = escalation_reason

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "response": self.response,
            "agent_type": self.agent_type,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "escalate": self.escalate,
            "escalation_reason": self.escalation_reason,
        }


def _rag_confidence_adjustment(rag_top_similarity: float | None) -> float:
    """Calculate confidence adjustment from RAG similarity score.

    Args:
        rag_top_similarity: Best similarity score, or None if RAG disabled.

    Returns:
        Adjustment value (positive = boost, negative = penalty).
    """
    if rag_top_similarity is None:
        return 0.0
    if rag_top_similarity > 0.85:
        return 0.10  # Strong RAG evidence
    if rag_top_similarity >= 0.70:
        return 0.05  # Moderate RAG evidence
    if rag_top_similarity == 0.0:
        return -0.05  # No RAG results when RAG is enabled
    return 0.0


def calculate_confidence_score(
    response: str,
    agent_type: str,
    has_critical_keywords: bool = False,
    llm_finish_reason: str | None = None,
    rag_top_similarity: float | None = None,
) -> float:
    """Calculate confidence score for an agent response.

    Args:
        response: The agent's response text
        agent_type: Type of agent
        has_critical_keywords: Whether critical keywords were detected
        llm_finish_reason: LLM finish reason (e.g., 'stop', 'length')
        rag_top_similarity: Best similarity score from RAG results (None if RAG disabled)

    Returns:
        Confidence score between 0 and 1
    """
    base_confidence = 0.85

    # Adjust based on finish reason
    if llm_finish_reason == "stop":
        base_confidence += 0.05
    elif llm_finish_reason == "length":
        base_confidence -= 0.10

    # Adjust based on response length (very short or very long may indicate issues)
    response_length = len(response)
    if response_length < 20:
        base_confidence -= 0.15
    elif response_length > 2000:
        base_confidence -= 0.05

    # Critical keywords reduce confidence (should escalate)
    if has_critical_keywords:
        base_confidence -= 0.30

    # RAG-based adjustments
    base_confidence += _rag_confidence_adjustment(rag_top_similarity)

    # Agent-specific adjustments
    if agent_type == "nurse_triage":
        base_confidence -= 0.05

    return max(0.0, min(1.0, base_confidence))


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(self, agent_type: str, llm_client: LLMClient | None = None):
        """Initialize the agent.

        Args:
            agent_type: Type identifier for this agent
            llm_client: Optional LLM client (uses singleton if not provided)
        """
        self.agent_type = agent_type
        self.llm_client = llm_client or get_llm_client()

    @abstractmethod
    async def process(
        self,
        message: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Process a message and return a result.

        Args:
            message: The patient's message
            context: Context dictionary with patient info, history, etc.

        Returns:
            AgentResult with response and metadata
        """
        pass

    def _build_messages(self, system_prompt: str, user_message: str) -> list[dict[str, str]]:
        """Build message list for LLM.

        Args:
            system_prompt: System instructions
            user_message: User's message

        Returns:
            List of message dicts for LLM API
        """
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    async def _call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        expect_json: bool = False,
    ) -> dict[str, Any]:
        """Call LLM with retry logic.

        Args:
            messages: Messages to send
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            expect_json: Whether to expect JSON response

        Returns:
            LLM response dict

        Raises:
            LLMError: If LLM call fails after retries
        """
        try:
            if expect_json:
                return await self.llm_client.generate_json(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            return await self.llm_client.generate(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except LLMError as e:
            logger.error(f"LLM call failed for {self.agent_type}: {e}")
            raise


class SupervisorAgent(BaseAgent):
    """Supervisor agent that routes messages to appropriate agents."""

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize supervisor agent."""
        super().__init__("supervisor", llm_client)

    async def process(
        self,
        message: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Analyze message and determine routing.

        Args:
            message: Patient's message
            context: Patient context including name, surgery info, etc.

        Returns:
            AgentResult with routing decision
        """
        patient = context.get("patient", {})

        prompt = build_supervisor_prompt(
            patient_name=patient.get("name", "Patient"),
            surgery_type=patient.get("surgery_type", "Unknown"),
            days_post_op=patient.get("days_post_op", 0),
            current_status=patient.get("status", "unknown"),
            recent_symptoms=patient.get("recent_symptoms", []),
            message=message,
        )

        messages = self._build_messages(
            system_prompt="You are the Care Supervisor. Route patient messages to the appropriate agent.",
            user_message=prompt,
        )

        try:
            response = await self._call_llm(messages, expect_json=True)

            # Parse routing decision
            routing = response if isinstance(response, dict) else json.loads(response.get("content", "{}"))

            return AgentResult(
                response=json.dumps(routing),
                agent_type="supervisor",
                metadata={
                    "routing": routing,
                    "target_agent": routing.get("agent", "care_coordinator"),
                    "urgency": routing.get("urgency", "routine"),
                },
                escalate=routing.get("escalate_to_human", False),
                escalation_reason=routing.get("reasoning", ""),
            )
        except (json.JSONDecodeError, LLMError) as e:
            logger.error(f"Supervisor routing failed: {e}")
            # Default to care coordinator on error
            return AgentResult(
                response=json.dumps(
                    {
                        "agent": "care_coordinator",
                        "urgency": "routine",
                        "escalate_to_human": False,
                        "reasoning": f"Routing failed: {e}",
                    }
                ),
                agent_type="supervisor",
                metadata={
                    "error": str(e),
                    "target_agent": "care_coordinator",
                    "urgency": "routine",
                },
                escalate=False,
            )


class CareCoordinatorAgent(BaseAgent):
    """Care Coordinator agent - warm, supportive patient interface."""

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize care coordinator agent."""
        super().__init__("care_coordinator", llm_client)

    async def process(
        self,
        message: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Process message with warm, supportive tone.

        Args:
            message: Patient's message
            context: Patient context

        Returns:
            AgentResult with supportive response
        """
        patient = context.get("patient", {})
        history = context.get("conversation_history", [])

        # Build patient context string
        patient_context = f"""
Name: {patient.get("name", "Patient")}
Surgery: {patient.get("surgery_type", "Unknown")} ({patient.get("days_post_op", 0)} days ago)
Status: {patient.get("status", "unknown")}
"""

        # Build conversation history
        history_str = "\n".join(
            [
                f"{msg.get('role', 'user').title()}: {msg.get('content', '')}"
                for msg in history[-5:]  # Last 5 messages
            ]
        )

        prompt = build_care_coordinator_prompt(
            patient_context=patient_context,
            conversation_history=history_str,
            message=message,
            rag_context=context.get("rag_context", ""),
        )

        messages = self._build_messages(
            system_prompt="You are the Care Coordinator. Be warm, supportive, and clear.",
            user_message=prompt,
        )

        try:
            response = await self._call_llm(messages, temperature=0.8)
            content = response.get("content", "I'm here to help. Could you tell me more?")

            # Calculate confidence score with RAG adjustment
            rag_top_sim = context.get("rag_top_similarity")
            confidence = calculate_confidence_score(
                response=content,
                agent_type="care_coordinator",
                llm_finish_reason=response.get("finish_reason"),
                rag_top_similarity=rag_top_sim,
            )

            # Check if confidence is below threshold
            should_escalate = confidence < 0.70

            return AgentResult(
                response=content,
                agent_type="care_coordinator",
                confidence=confidence,
                metadata={
                    "usage": response.get("usage", {}),
                    "confidence_score": confidence,
                },
                escalate=should_escalate,
                escalation_reason="Low confidence score" if should_escalate else "",
            )
        except LLMError as e:
            logger.error(f"Care Coordinator failed: {e}")
            return AgentResult(
                response="I'm having trouble right now. Let me connect you with a nurse who can help.",
                agent_type="care_coordinator",
                escalate=True,
                escalation_reason=f"LLM error: {e}",
            )


class NurseTriageAgent(BaseAgent):
    """Nurse Triage agent - clinical assessment and guidance."""

    # Critical symptoms that require immediate escalation
    # Using regex patterns for flexibility with human language variations
    CRITICAL_PATTERNS = [
        # Pain levels 8-10 (catches: "pain is 10", "10 out of 10 pain", "pain level 9")
        # Must be standalone numbers, not part of fractions like "4/10"
        (r"\bpain\b[^0-9/.]*\b(8|9|10)\b(?:\s*(?:/|out\s+of)\s*10)?(?!\d)", "severe pain (8-10/10)"),
        (r"\b(8|9|10)\b(?:\s*(?:/|out\s+of)\s*10)?[^0-9/.]*\bpain\b", "severe pain (8-10/10)"),
        (r"\bpain\s+(level\s+)?(8|9|10)\b(?:\s*/\s*10)?\b", "severe pain (8-10/10)"),
        # Severe pain variations
        (r"severe\s+pain|unbearable\s+pain|intense\s+pain|excruciating", "severe pain description"),
        # Bleeding
        (r"\b(bleeding|blood)\b", "bleeding"),
        # Fever 102+ (catches: "fever is 103", "103 degree fever", "temp of 104")
        # Must be standalone temperature, not part of other numbers
        (r"\bfever\b[^0-9/.]*\b(10[2-9]|11[0-9])\b(?!\d)", "high fever (102°F+)"),
        (r"\b(10[2-9]|11[0-9])\b[^0-9/.]*\bfever\b", "high fever (102°F+)"),
        (r"\btemp(?:erature)?\b[^0-9/.]*\b(10[2-9]|11[0-9])\b", "high fever (102°F+)"),
        # Chest pain / cardiac
        (r"\b(chest\s+pain|heart\s+attack|cardiac\s+arrest)\b", "chest pain/cardiac"),
        # Breathing difficulties
        (
            r"can't\s+breathe|cannot\s+breathe|breathing\s+difficulty|"
            r"shortness\s+of\s+breath|difficulty\s+breathing|wheezing|struggling\s+to\s+breathe",
            "breathing difficulty",
        ),
        # Unconsciousness
        (r"unconscious|passed\s+out|fainted|blackout", "loss of consciousness"),
        # Vomiting blood
        (r"vomiting\s+blood|coughing\s+blood|blood\s+in\s+vomit", "hematemesis"),
        # Allergic reaction
        (r"allergic\s+reaction|anaphylaxis|swelling\s+throat", "allergic reaction"),
        # Suicide/self-harm
        (r"suicide|kill\s+myself|end\s+my\s+life", "self-harm ideation"),
    ]

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize nurse triage agent."""
        super().__init__("nurse_triage", llm_client)

    def _check_critical_symptoms(self, message: str) -> tuple[bool, str]:
        """Check for critical symptoms requiring immediate escalation.

        Uses regex patterns to catch variations in human language.
        This is a safety net - the LLM should also detect these.

        Args:
            message: Patient's message

        Returns:
            Tuple of (is_critical, reason)
        """
        message_lower = message.lower()
        matched_by = None

        for pattern, description in self.CRITICAL_PATTERNS:
            if re.search(pattern, message_lower):
                matched_by = f"regex pattern: {description}"
                logger.info(f"Critical symptom detected by {matched_by}: {message[:50]}...")
                return True, f"Critical symptom detected: {description}"

        return False, ""

    async def process(
        self,
        message: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Process message with clinical assessment.

        Args:
            message: Patient's message
            context: Patient context including pathway info

        Returns:
            AgentResult with clinical assessment
        """
        # First check for critical symptoms
        is_critical, critical_reason = self._check_critical_symptoms(message)
        if is_critical:
            return AgentResult(
                response="I'm connecting you with a nurse right away. This needs immediate attention.",
                agent_type="nurse_triage",
                escalate=True,
                escalation_reason=critical_reason,
                metadata={"severity": "red", "auto_triggered": True},
            )

        patient = context.get("patient", {})
        pathway = context.get("pathway", {})

        prompt = build_nurse_triage_prompt(
            surgery_type=patient.get("surgery_type", "Unknown"),
            surgery_date=patient.get("surgery_date", "Unknown"),
            days_post_op=patient.get("days_post_op", 0),
            current_phase=pathway.get("current_phase", "unknown"),
            medications=patient.get("medications", []),
            allergies=patient.get("allergies", []),
            pathway_context=json.dumps(pathway, indent=2),
            message=message,
            rag_context=context.get("rag_context", ""),
        )

        messages = self._build_messages(
            system_prompt="You are the Nurse Triage Agent. Provide clinical assessment and guidance.",
            user_message=prompt,
        )

        try:
            response = await self._call_llm(messages, temperature=0.5, expect_json=True)

            # Parse JSON response
            if isinstance(response, dict) and "content" in response:
                result = json.loads(response["content"])
            else:
                result = response

            severity = result.get("severity", "green")
            response_text = result.get("response", result.get("recommendation", ""))

            # Calculate confidence score with RAG adjustment
            rag_top_sim = context.get("rag_top_similarity")
            confidence = calculate_confidence_score(
                response=response_text,
                agent_type="nurse_triage",
                has_critical_keywords=severity in ["orange", "red"],
                llm_finish_reason=response.get("finish_reason"),
                rag_top_similarity=rag_top_sim,
            )

            # Escalate if severity is high or confidence is low
            escalate = result.get("escalate", False) or severity in ["orange", "red"] or confidence < 0.70

            return AgentResult(
                response=response_text,
                agent_type="nurse_triage",
                confidence=confidence,
                metadata={
                    "severity": severity,
                    "assessment": result.get("assessment", ""),
                    "action_items": result.get("action_items", []),
                    "confidence_score": confidence,
                },
                escalate=escalate,
                escalation_reason=result.get("escalation_reason", "")
                or ("Low confidence score" if confidence < 0.70 else ""),
            )
        except (json.JSONDecodeError, LLMError) as e:
            logger.error(f"Nurse Triage failed: {e}")
            return AgentResult(
                response="I'm having trouble assessing your symptoms. Let me get a nurse to help you.",
                agent_type="nurse_triage",
                escalate=True,
                escalation_reason=f"LLM error: {e}",
            )


class DocumentationAgent(BaseAgent):
    """Documentation agent - creates structured summaries."""

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize documentation agent."""
        super().__init__("documentation", llm_client)

    async def process(
        self,
        message: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Create documentation from conversation.

        Args:
            message: Not used - documentation is based on context
            context: Conversation context with transcript, actions, etc.

        Returns:
            AgentResult with structured documentation
        """
        patient = context.get("patient", {})
        transcript = context.get("transcript", "")
        actions = context.get("actions", [])
        outcome = context.get("outcome", "")
        duration = context.get("duration", "unknown")

        prompt = build_documentation_prompt(
            patient_name=patient.get("name", "Unknown"),
            interaction_type=context.get("interaction_type", "Chat"),
            duration=duration,
            conversation_transcript=transcript,
            actions_taken=actions,
            outcome=outcome,
        )

        messages = self._build_messages(
            system_prompt="You are the Documentation Agent. Create clear, structured summaries.",
            user_message=prompt,
        )

        try:
            response = await self._call_llm(messages, temperature=0.3)
            content = response.get("content", "")

            return AgentResult(
                response=content,
                agent_type="documentation",
                confidence=0.95,
                metadata={"usage": response.get("usage", {})},
            )
        except LLMError as e:
            logger.error(f"Documentation failed: {e}")
            return AgentResult(
                response="Documentation generation failed.",
                agent_type="documentation",
                confidence=0.0,
            )


class PlaceholderSpecialistAgent(BaseAgent):
    """Placeholder specialist that routes to human experts."""

    SPECIALTIES = {
        "specialist_cardiology": "Cardiology",
        "specialist_social_work": "Social Work",
        "specialist_nutrition": "Nutrition",
        "specialist_pt_rehab": "PT/Rehab",
        "specialist_palliative": "Palliative Care",
        "specialist_pharmacy": "Pharmacy",
    }

    def __init__(self, specialty: str, llm_client: LLMClient | None = None):
        """Initialize placeholder specialist.

        Args:
            specialty: The specialty type
            llm_client: Optional LLM client
        """
        super().__init__(specialty, llm_client)
        self.specialty_name = self.SPECIALTIES.get(specialty, "Specialist")

    async def process(
        self,
        message: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Route to human specialist.

        Args:
            message: Patient's message
            context: Patient context

        Returns:
            AgentResult with escalation
        """
        prompt = build_placeholder_specialist_prompt(self.specialty_name, message)

        messages = self._build_messages(
            system_prompt=f"You are the {self.specialty_name} specialist.",
            user_message=prompt,
        )

        try:
            response = await self._call_llm(messages, temperature=0.7, expect_json=True)

            if isinstance(response, dict) and "content" in response:
                result = json.loads(response["content"])
            else:
                result = response

            return AgentResult(
                response=result.get(
                    "response",
                    f"I'd like to connect you with our {self.specialty_name} team who can best help with this.",
                ),
                agent_type=self.agent_type,
                escalate=True,
                escalation_reason=f"Routed to {self.specialty_name} specialist",
                metadata={
                    "specialty": self.specialty_name,
                    "notes": result.get("notes", ""),
                },
            )
        except (json.JSONDecodeError, LLMError):
            # Fallback response
            return AgentResult(
                response=f"I'd like to connect you with our {self.specialty_name} team who can best help with this.",
                agent_type=self.agent_type,
                escalate=True,
                escalation_reason=f"Routed to {self.specialty_name} specialist",
            )


# Factory function to get agent by type
def get_agent(agent_type: str, llm_client: LLMClient | None = None) -> BaseAgent:
    """Get an agent instance by type.

    Args:
        agent_type: Type of agent to create
        llm_client: Optional LLM client

    Returns:
        Agent instance

    Raises:
        ValueError: If agent type is unknown
    """
    from apps.agents.specialists import SPECIALIST_REGISTRY

    core_agents: dict[str, type[BaseAgent]] = {
        "supervisor": SupervisorAgent,
        "care_coordinator": CareCoordinatorAgent,
        "nurse_triage": NurseTriageAgent,
        "documentation": DocumentationAgent,
    }

    if agent_type in core_agents:
        return core_agents[agent_type](llm_client)

    if agent_type in SPECIALIST_REGISTRY:
        return SPECIALIST_REGISTRY[agent_type](llm_client)

    raise ValueError(f"Unknown agent type: {agent_type}")
