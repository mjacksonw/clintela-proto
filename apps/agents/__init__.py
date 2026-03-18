"""Agents app - Multi-agent AI system for patient care coordination."""

from apps.agents.agents import (
    AgentResult,
    BaseAgent,
    CareCoordinatorAgent,
    DocumentationAgent,
    NurseTriageAgent,
    PlaceholderSpecialistAgent,
    SupervisorAgent,
    get_agent,
)
from apps.agents.llm_client import LLMClient, MockLLMClient, get_llm_client
from apps.agents.workflow import AgentWorkflow, get_workflow

__all__ = [
    # Agents
    "AgentResult",
    "BaseAgent",
    "SupervisorAgent",
    "CareCoordinatorAgent",
    "NurseTriageAgent",
    "DocumentationAgent",
    "PlaceholderSpecialistAgent",
    "get_agent",
    # LLM Client
    "LLMClient",
    "MockLLMClient",
    "get_llm_client",
    # Workflow
    "AgentWorkflow",
    "get_workflow",
]
