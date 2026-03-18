"""LangGraph workflow for multi-agent orchestration."""

import json
import logging
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from apps.agents.agents import (
    AgentResult,
    CareCoordinatorAgent,
    DocumentationAgent,
    NurseTriageAgent,
    PlaceholderSpecialistAgent,
    SupervisorAgent,
)
from apps.agents.llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class AgentWorkflow:
    """LangGraph-based workflow for agent orchestration."""

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize the workflow.

        Args:
            llm_client: Optional LLM client
        """
        self.llm_client = llm_client or get_llm_client()
        self.supervisor = SupervisorAgent(self.llm_client)
        self.care_coordinator = CareCoordinatorAgent(self.llm_client)
        self.nurse_triage = NurseTriageAgent(self.llm_client)
        self.documentation = DocumentationAgent(self.llm_client)

        # Specialist agents (placeholders)
        self.specialists = {
            "specialist_cardiology": PlaceholderSpecialistAgent("specialist_cardiology", self.llm_client),
            "specialist_social_work": PlaceholderSpecialistAgent("specialist_social_work", self.llm_client),
            "specialist_nutrition": PlaceholderSpecialistAgent("specialist_nutrition", self.llm_client),
            "specialist_pt_rehab": PlaceholderSpecialistAgent("specialist_pt_rehab", self.llm_client),
            "specialist_palliative": PlaceholderSpecialistAgent("specialist_palliative", self.llm_client),
            "specialist_pharmacy": PlaceholderSpecialistAgent("specialist_pharmacy", self.llm_client),
        }

        self._workflow: CompiledStateGraph | None = None

    def _get_workflow(self) -> CompiledStateGraph:
        """Get or create the compiled workflow.

        Returns:
            Compiled StateGraph
        """
        if self._workflow is not None:
            return self._workflow

        # Define state schema
        from typing import TypedDict

        class AgentState(TypedDict):
            message: str
            context: dict[str, Any]
            routing: dict[str, Any]
            result: dict[str, Any]
            should_escalate: bool
            escalation_reason: str

        # Build the graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("supervisor", self._supervisor_node)
        workflow.add_node("care_coordinator", self._care_coordinator_node)
        workflow.add_node("nurse_triage", self._nurse_triage_node)
        workflow.add_node("specialist", self._specialist_node)
        workflow.add_node("documentation", self._documentation_node)
        workflow.add_node("escalate", self._escalation_node)

        # Define edges
        workflow.set_entry_point("supervisor")

        # Conditional routing from supervisor
        workflow.add_conditional_edges(
            "supervisor",
            self._route_from_supervisor,
            {
                "care_coordinator": "care_coordinator",
                "nurse_triage": "nurse_triage",
                "specialist": "specialist",
                "escalate": "escalate",
            },
        )

        # All agents go to documentation (for logging)
        workflow.add_edge("care_coordinator", "documentation")
        workflow.add_edge("nurse_triage", "documentation")
        workflow.add_edge("specialist", "documentation")

        # Documentation ends
        workflow.add_edge("documentation", END)
        workflow.add_edge("escalate", END)

        # Compile
        self._workflow = workflow.compile()
        return self._workflow

    async def _supervisor_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Supervisor node - routes messages to appropriate agents.

        Args:
            state: Current workflow state

        Returns:
            Updated state with routing decision
        """
        message = state.get("message", "")
        context = state.get("context", {})

        try:
            result = await self.supervisor.process(message, context)
            routing = json.loads(result.response) if isinstance(result.response, str) else result.response

            return {
                **state,
                "routing": routing,
                "should_escalate": result.escalate,
                "escalation_reason": result.escalation_reason,
            }
        except Exception as e:
            logger.error(f"Supervisor node failed: {e}")
            return {
                **state,
                "routing": {"agent": "care_coordinator", "urgency": "routine"},
                "should_escalate": False,
            }

    def _route_from_supervisor(self, state: dict[str, Any]) -> str:
        """Determine next node based on supervisor routing.

        Args:
            state: Current workflow state

        Returns:
            Next node name
        """
        routing = state.get("routing", {})
        should_escalate = state.get("should_escalate", False)

        if should_escalate:
            return "escalate"

        agent = routing.get("agent", "care_coordinator")

        if agent == "care_coordinator":
            return "care_coordinator"
        elif agent == "nurse_triage":
            return "nurse_triage"
        elif agent.startswith("specialist_"):
            # Store which specialist for later
            state["target_specialist"] = agent
            return "specialist"
        else:
            return "care_coordinator"

    async def _care_coordinator_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Care Coordinator node - handles routine patient interactions.

        Args:
            state: Current workflow state

        Returns:
            Updated state with agent result
        """
        message = state.get("message", "")
        context = state.get("context", {})

        try:
            result = await self.care_coordinator.process(message, context)
            return {
                **state,
                "result": result.to_dict(),
                "should_escalate": result.escalate,
                "escalation_reason": result.escalation_reason,
            }
        except Exception as e:
            logger.error(f"Care Coordinator node failed: {e}")
            return {
                **state,
                "result": {
                    "response": "I'm having trouble. Let me connect you with a nurse.",
                    "agent_type": "care_coordinator",
                    "escalate": True,
                },
                "should_escalate": True,
                "escalation_reason": f"Agent error: {e}",
            }

    async def _nurse_triage_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Nurse Triage node - handles clinical assessments.

        Args:
            state: Current workflow state

        Returns:
            Updated state with agent result
        """
        message = state.get("message", "")
        context = state.get("context", {})

        try:
            result = await self.nurse_triage.process(message, context)
            return {
                **state,
                "result": result.to_dict(),
                "should_escalate": result.escalate,
                "escalation_reason": result.escalation_reason,
            }
        except Exception as e:
            logger.error(f"Nurse Triage node failed: {e}")
            return {
                **state,
                "result": {
                    "response": "I'm having trouble assessing your symptoms. A nurse will help you.",
                    "agent_type": "nurse_triage",
                    "escalate": True,
                },
                "should_escalate": True,
                "escalation_reason": f"Agent error: {e}",
            }

    async def _specialist_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Specialist node - routes to domain-specific specialists.

        Args:
            state: Current workflow state

        Returns:
            Updated state with agent result
        """
        message = state.get("message", "")
        context = state.get("context", {})
        specialist_type = state.get("target_specialist", "specialist_cardiology")

        agent = self.specialists.get(specialist_type, self.specialists["specialist_cardiology"])

        try:
            result = await agent.process(message, context)
            return {
                **state,
                "result": result.to_dict(),
                "should_escalate": True,  # Specialists always escalate
                "escalation_reason": f"Routed to {specialist_type}",
            }
        except Exception as e:
            logger.error(f"Specialist node failed: {e}")
            return {
                **state,
                "result": {
                    "response": "I'll connect you with a specialist who can help.",
                    "agent_type": specialist_type,
                    "escalate": True,
                },
                "should_escalate": True,
                "escalation_reason": f"Routed to {specialist_type}",
            }

    async def _documentation_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Documentation node - creates interaction summary.

        Args:
            state: Current workflow state

        Returns:
            Updated state with documentation
        """
        result = state.get("result", {})

        # Create minimal documentation
        doc = {
            "agent_type": result.get("agent_type", "unknown"),
            "response": result.get("response", ""),
            "escalated": state.get("should_escalate", False),
            "escalation_reason": state.get("escalation_reason", ""),
        }

        return {
            **state,
            "documentation": doc,
        }

    async def _escalation_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Escalation node - handles human handoff.

        Args:
            state: Current workflow state

        Returns:
            Updated state with escalation info
        """
        return {
            **state,
            "result": {
                "response": "I'm connecting you with a nurse right away.",
                "agent_type": "escalation",
                "escalate": True,
                "escalation_reason": state.get("escalation_reason", "Unknown"),
            },
        }

    async def process_message(
        self,
        message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Process a patient message through the workflow.

        Args:
            message: Patient's message
            context: Patient context

        Returns:
            Workflow result with response and metadata
        """
        workflow = self._get_workflow()

        initial_state = {
            "message": message,
            "context": context,
            "routing": {},
            "result": {},
            "should_escalate": False,
            "escalation_reason": "",
        }

        try:
            result = await workflow.ainvoke(initial_state)
            return {
                "response": result.get("result", {}).get("response", ""),
                "agent_type": result.get("result", {}).get("agent_type", "unknown"),
                "escalate": result.get("should_escalate", False),
                "escalation_reason": result.get("escalation_reason", ""),
                "metadata": result.get("result", {}).get("metadata", {}),
                "routing": result.get("routing", {}),
            }
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            return {
                "response": "I'm having trouble right now. Let me connect you with a nurse.",
                "agent_type": "error",
                "escalate": True,
                "escalation_reason": f"Workflow error: {e}",
                "metadata": {},
            }


# Singleton workflow instance
_workflow_instance: AgentWorkflow | None = None


def get_workflow() -> AgentWorkflow:
    """Get the singleton workflow instance."""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = AgentWorkflow()
    return _workflow_instance


def reset_workflow():
    """Reset the workflow instance (useful for testing)."""
    global _workflow_instance
    _workflow_instance = None
