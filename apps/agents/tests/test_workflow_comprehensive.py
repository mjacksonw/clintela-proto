"""Comprehensive tests for AgentWorkflow and related functions."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from apps.agents.workflow import (
    AgentWorkflow,
    get_workflow,
    reset_workflow,
)
from apps.agents.agents import AgentResult


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock()
    client.generate = AsyncMock(
        return_value={
            "content": "Test response",
            "finish_reason": "stop",
        }
    )
    client.generate_json = AsyncMock(
        return_value={
            "content": json.dumps({"agent": "care_coordinator", "urgency": "routine"}),
        }
    )
    return client


@pytest.fixture
def mock_agent_result():
    """Create a mock AgentResult."""
    return AgentResult(
        response='{"agent": "care_coordinator", "urgency": "routine"}',
        agent_type="supervisor",
        confidence=0.9,
        metadata={"target_agent": "care_coordinator"},
        escalate=False,
        escalation_reason="",
    )


@pytest.fixture
def mock_compiled_workflow():
    """Create a mock compiled workflow."""
    workflow = AsyncMock()
    workflow.ainvoke = AsyncMock(
        return_value={
            "message": "Test message",
            "context": {},
            "routing": {"agent": "care_coordinator"},
            "result": {
                "response": "Test response",
                "agent_type": "care_coordinator",
                "escalate": False,
            },
            "should_escalate": False,
            "escalation_reason": "",
        }
    )
    return workflow


class TestAgentWorkflowInit:
    """Tests for AgentWorkflow initialization."""

    def test_init_with_default_llm_client(self):
        """Test initialization with default LLM client."""
        with patch("apps.agents.workflow.get_llm_client") as mock_get_llm:
            mock_client = Mock()
            mock_get_llm.return_value = mock_client

            workflow = AgentWorkflow()

            assert workflow.llm_client == mock_client
            assert workflow._workflow is None
            assert "specialist_cardiology" in workflow.specialists
            assert "specialist_social_work" in workflow.specialists
            assert "specialist_nutrition" in workflow.specialists
            assert "specialist_pt_rehab" in workflow.specialists
            assert "specialist_palliative" in workflow.specialists
            assert "specialist_pharmacy" in workflow.specialists

    def test_init_with_custom_llm_client(self, mock_llm_client):
        """Test initialization with custom LLM client."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        assert workflow.llm_client == mock_llm_client
        assert workflow._workflow is None

    def test_agents_initialized(self, mock_llm_client):
        """Test that all agents are initialized."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        assert workflow.supervisor is not None
        assert workflow.care_coordinator is not None
        assert workflow.nurse_triage is not None
        assert workflow.documentation is not None
        assert len(workflow.specialists) == 6


class TestAgentWorkflowGetWorkflow:
    """Tests for _get_workflow method."""

    @patch("apps.agents.workflow.StateGraph")
    def test_get_workflow_creates_new(self, mock_state_graph_class, mock_llm_client):
        """Test that _get_workflow creates a new workflow when none exists."""
        mock_workflow = Mock()
        mock_workflow.compile.return_value = Mock()
        mock_state_graph_class.return_value = mock_workflow

        workflow = AgentWorkflow(llm_client=mock_llm_client)
        result = workflow._get_workflow()

        assert result is not None
        assert workflow._workflow is not None
        mock_workflow.add_node.assert_called()
        mock_workflow.set_entry_point.assert_called_once_with("supervisor")
        mock_workflow.add_conditional_edges.assert_called_once()
        mock_workflow.add_edge.assert_called()
        mock_workflow.compile.assert_called_once()

    @patch("apps.agents.workflow.StateGraph")
    def test_get_workflow_returns_cached(self, mock_state_graph_class, mock_llm_client):
        """Test that _get_workflow returns cached workflow if exists."""
        mock_compiled = Mock()
        mock_workflow = Mock()
        mock_workflow.compile.return_value = mock_compiled
        mock_state_graph_class.return_value = mock_workflow

        workflow = AgentWorkflow(llm_client=mock_llm_client)

        # First call
        result1 = workflow._get_workflow()
        # Second call should return cached
        result2 = workflow._get_workflow()

        assert result1 == result2
        mock_workflow.compile.assert_called_once()

    @patch("apps.agents.workflow.StateGraph")
    def test_workflow_structure(self, mock_state_graph_class, mock_llm_client):
        """Test that workflow has correct structure."""
        mock_workflow = Mock()
        mock_compiled = Mock()
        mock_workflow.compile.return_value = mock_compiled
        mock_state_graph_class.return_value = mock_workflow

        workflow = AgentWorkflow(llm_client=mock_llm_client)
        workflow._get_workflow()

        # Check all nodes are added
        expected_nodes = [
            "supervisor",
            "care_coordinator",
            "nurse_triage",
            "specialist",
            "documentation",
            "escalate",
        ]
        for node in expected_nodes:
            mock_workflow.add_node.assert_any_call(
                node, getattr(workflow, f"_{node}_node" if node != "escalate" else "_escalation_node")
            )

        # Check edges
        mock_workflow.set_entry_point.assert_called_once_with("supervisor")
        mock_workflow.add_edge.assert_any_call("care_coordinator", "documentation")
        mock_workflow.add_edge.assert_any_call("nurse_triage", "documentation")
        mock_workflow.add_edge.assert_any_call("specialist", "documentation")


class TestSupervisorNode:
    """Tests for _supervisor_node method."""

    @pytest.mark.asyncio
    async def test_supervisor_node_success(self, mock_llm_client, mock_agent_result):
        """Test successful supervisor node execution."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        with patch.object(workflow.supervisor, "process", AsyncMock(return_value=mock_agent_result)):
            state = {
                "message": "Test message",
                "context": {"patient": {"name": "John"}},
            }

            result = await workflow._supervisor_node(state)

            assert "routing" in result
            assert result["routing"]["agent"] == "care_coordinator"
            assert result["should_escalate"] is False
            assert result["escalation_reason"] == ""

    @pytest.mark.asyncio
    async def test_supervisor_node_with_dict_response(self, mock_llm_client):
        """Test supervisor node with dict response (not JSON string)."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_result = AgentResult(
            response={"agent": "nurse_triage", "urgency": "urgent"},
            agent_type="supervisor",
            escalate=True,
            escalation_reason="Critical symptoms",
        )

        with patch.object(workflow.supervisor, "process", AsyncMock(return_value=mock_result)):
            state = {
                "message": "I have chest pain",
                "context": {},
            }

            result = await workflow._supervisor_node(state)

            assert result["routing"]["agent"] == "nurse_triage"
            assert result["should_escalate"] is True
            assert result["escalation_reason"] == "Critical symptoms"

    @pytest.mark.asyncio
    async def test_supervisor_node_error_recovery(self, mock_llm_client):
        """Test supervisor node error recovery."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        with patch.object(workflow.supervisor, "process", AsyncMock(side_effect=Exception("LLM error"))):
            state = {
                "message": "Test",
                "context": {},
            }

            result = await workflow._supervisor_node(state)

            assert result["routing"]["agent"] == "care_coordinator"
            assert result["routing"]["urgency"] == "routine"
            assert result["should_escalate"] is False

    @pytest.mark.asyncio
    async def test_supervisor_node_preserves_state(self, mock_llm_client, mock_agent_result):
        """Test that supervisor node preserves existing state."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        with patch.object(workflow.supervisor, "process", AsyncMock(return_value=mock_agent_result)):
            state = {
                "message": "Test",
                "context": {"extra": "data"},
                "existing_key": "value",
            }

            result = await workflow._supervisor_node(state)

            assert result["existing_key"] == "value"
            assert result["context"]["extra"] == "data"


class TestRouteFromSupervisor:
    """Tests for _route_from_supervisor method."""

    def test_route_escalation(self, mock_llm_client):
        """Test routing to escalation when should_escalate is True."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {"agent": "care_coordinator"},
            "should_escalate": True,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "escalate"

    def test_route_care_coordinator(self, mock_llm_client):
        """Test routing to care coordinator."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {"agent": "care_coordinator"},
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "care_coordinator"

    def test_route_nurse_triage(self, mock_llm_client):
        """Test routing to nurse triage."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {"agent": "nurse_triage"},
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "nurse_triage"

    def test_route_specialist_cardiology(self, mock_llm_client):
        """Test routing to specialist (cardiology)."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {"agent": "specialist_cardiology"},
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "specialist"
        assert state["target_specialist"] == "specialist_cardiology"

    def test_route_specialist_social_work(self, mock_llm_client):
        """Test routing to specialist (social work)."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {"agent": "specialist_social_work"},
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "specialist"
        assert state["target_specialist"] == "specialist_social_work"

    def test_route_specialist_nutrition(self, mock_llm_client):
        """Test routing to specialist (nutrition)."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {"agent": "specialist_nutrition"},
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "specialist"
        assert state["target_specialist"] == "specialist_nutrition"

    def test_route_specialist_pt_rehab(self, mock_llm_client):
        """Test routing to specialist (PT/rehab)."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {"agent": "specialist_pt_rehab"},
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "specialist"
        assert state["target_specialist"] == "specialist_pt_rehab"

    def test_route_specialist_palliative(self, mock_llm_client):
        """Test routing to specialist (palliative)."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {"agent": "specialist_palliative"},
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "specialist"
        assert state["target_specialist"] == "specialist_palliative"

    def test_route_specialist_pharmacy(self, mock_llm_client):
        """Test routing to specialist (pharmacy)."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {"agent": "specialist_pharmacy"},
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "specialist"
        assert state["target_specialist"] == "specialist_pharmacy"

    def test_route_default_to_care_coordinator(self, mock_llm_client):
        """Test default routing to care coordinator for unknown agents."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {"agent": "unknown_agent"},
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "care_coordinator"

    def test_route_empty_routing(self, mock_llm_client):
        """Test routing with empty routing dict."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "routing": {},
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "care_coordinator"

    def test_route_missing_routing(self, mock_llm_client):
        """Test routing with missing routing key."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "should_escalate": False,
        }

        result = workflow._route_from_supervisor(state)

        assert result == "care_coordinator"


class TestCareCoordinatorNode:
    """Tests for _care_coordinator_node method."""

    @pytest.mark.asyncio
    async def test_care_coordinator_success(self, mock_llm_client):
        """Test successful care coordinator node execution."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_result = AgentResult(
            response="I'm here to help with your recovery.",
            agent_type="care_coordinator",
            confidence=0.9,
            escalate=False,
        )

        with patch.object(workflow.care_coordinator, "process", AsyncMock(return_value=mock_result)):
            state = {
                "message": "When can I shower?",
                "context": {"patient": {"name": "John"}},
            }

            result = await workflow._care_coordinator_node(state)

            assert "result" in result
            assert result["result"]["response"] == "I'm here to help with your recovery."
            assert result["result"]["agent_type"] == "care_coordinator"
            assert result["should_escalate"] is False

    @pytest.mark.asyncio
    async def test_care_coordinator_escalation(self, mock_llm_client):
        """Test care coordinator node with escalation."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_result = AgentResult(
            response="I need to connect you with a nurse.",
            agent_type="care_coordinator",
            confidence=0.6,
            escalate=True,
            escalation_reason="Low confidence",
        )

        with patch.object(workflow.care_coordinator, "process", AsyncMock(return_value=mock_result)):
            state = {
                "message": "Complex question",
                "context": {},
            }

            result = await workflow._care_coordinator_node(state)

            assert result["should_escalate"] is True
            assert result["escalation_reason"] == "Low confidence"

    @pytest.mark.asyncio
    async def test_care_coordinator_error_recovery(self, mock_llm_client):
        """Test care coordinator node error recovery."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        with patch.object(workflow.care_coordinator, "process", AsyncMock(side_effect=Exception("Agent error"))):
            state = {
                "message": "Test",
                "context": {},
            }

            result = await workflow._care_coordinator_node(state)

            assert result["should_escalate"] is True
            assert "Agent error" in result["escalation_reason"]
            assert result["result"]["agent_type"] == "care_coordinator"
            assert "escalate" in result["result"]
            assert result["result"]["escalate"] is True


class TestNurseTriageNode:
    """Tests for _nurse_triage_node method."""

    @pytest.mark.asyncio
    async def test_nurse_triage_success(self, mock_llm_client):
        """Test successful nurse triage node execution."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_result = AgentResult(
            response="Your symptoms are normal for this stage.",
            agent_type="nurse_triage",
            confidence=0.85,
            escalate=False,
        )

        with patch.object(workflow.nurse_triage, "process", AsyncMock(return_value=mock_result)):
            state = {
                "message": "I have some pain",
                "context": {"patient": {"name": "John"}},
            }

            result = await workflow._nurse_triage_node(state)

            assert "result" in result
            assert result["result"]["agent_type"] == "nurse_triage"
            assert result["should_escalate"] is False

    @pytest.mark.asyncio
    async def test_nurse_triage_escalation(self, mock_llm_client):
        """Test nurse triage node with escalation."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_result = AgentResult(
            response="This needs immediate attention.",
            agent_type="nurse_triage",
            confidence=0.9,
            escalate=True,
            escalation_reason="Critical symptoms detected",
        )

        with patch.object(workflow.nurse_triage, "process", AsyncMock(return_value=mock_result)):
            state = {
                "message": "Severe chest pain",
                "context": {},
            }

            result = await workflow._nurse_triage_node(state)

            assert result["should_escalate"] is True
            assert result["escalation_reason"] == "Critical symptoms detected"

    @pytest.mark.asyncio
    async def test_nurse_triage_error_recovery(self, mock_llm_client):
        """Test nurse triage node error recovery."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        with patch.object(workflow.nurse_triage, "process", AsyncMock(side_effect=Exception("Triage error"))):
            state = {
                "message": "Test",
                "context": {},
            }

            result = await workflow._nurse_triage_node(state)

            assert result["should_escalate"] is True
            assert "Agent error" in result["escalation_reason"]
            assert result["result"]["agent_type"] == "nurse_triage"


class TestSpecialistNode:
    """Tests for _specialist_node method."""

    @pytest.mark.asyncio
    async def test_specialist_cardiology(self, mock_llm_client):
        """Test specialist node with cardiology."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_result = AgentResult(
            response="I'll connect you with cardiology.",
            agent_type="specialist_cardiology",
            escalate=True,
            escalation_reason="Routed to Cardiology specialist",
        )

        with patch.object(
            workflow.specialists["specialist_cardiology"], "process", AsyncMock(return_value=mock_result)
        ):
            state = {
                "message": "Heart palpitations",
                "context": {},
                "target_specialist": "specialist_cardiology",
            }

            result = await workflow._specialist_node(state)

            assert result["result"]["agent_type"] == "specialist_cardiology"
            assert result["should_escalate"] is True
            assert "cardiology" in result["escalation_reason"].lower()

    @pytest.mark.asyncio
    async def test_specialist_default_to_cardiology(self, mock_llm_client):
        """Test specialist node defaults to cardiology when target not found."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_result = AgentResult(
            response="I'll connect you with a specialist.",
            agent_type="specialist_cardiology",
            escalate=True,
        )

        with patch.object(
            workflow.specialists["specialist_cardiology"], "process", AsyncMock(return_value=mock_result)
        ):
            state = {
                "message": "Question",
                "context": {},
                "target_specialist": "nonexistent_specialist",
            }

            result = await workflow._specialist_node(state)

            assert result["result"]["agent_type"] == "specialist_cardiology"

    @pytest.mark.asyncio
    async def test_specialist_no_target_specialist(self, mock_llm_client):
        """Test specialist node when no target_specialist in state."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_result = AgentResult(
            response="I'll connect you with a specialist.",
            agent_type="specialist_cardiology",
            escalate=True,
        )

        with patch.object(
            workflow.specialists["specialist_cardiology"], "process", AsyncMock(return_value=mock_result)
        ):
            state = {
                "message": "Question",
                "context": {},
            }

            result = await workflow._specialist_node(state)

            assert result["result"]["agent_type"] == "specialist_cardiology"

    @pytest.mark.asyncio
    async def test_specialist_error_recovery(self, mock_llm_client):
        """Test specialist node error recovery."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        with patch.object(
            workflow.specialists["specialist_cardiology"],
            "process",
            AsyncMock(side_effect=Exception("Specialist error")),
        ):
            state = {
                "message": "Test",
                "context": {},
                "target_specialist": "specialist_cardiology",
            }

            result = await workflow._specialist_node(state)

            assert result["should_escalate"] is True
            assert result["result"]["agent_type"] == "specialist_cardiology"
            assert "escalate" in result["result"]

    @pytest.mark.asyncio
    async def test_all_specialist_types(self, mock_llm_client):
        """Test all specialist types are available."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        specialist_types = [
            "specialist_cardiology",
            "specialist_social_work",
            "specialist_nutrition",
            "specialist_pt_rehab",
            "specialist_palliative",
            "specialist_pharmacy",
        ]

        for specialist_type in specialist_types:
            mock_result = AgentResult(
                response=f"Routing to {specialist_type}.",
                agent_type=specialist_type,
                escalate=True,
                escalation_reason=f"Routed to {specialist_type}",
            )

            with patch.object(workflow.specialists[specialist_type], "process", AsyncMock(return_value=mock_result)):
                state = {
                    "message": "Test",
                    "context": {},
                    "target_specialist": specialist_type,
                }

                result = await workflow._specialist_node(state)

                assert result["result"]["agent_type"] == specialist_type
                assert result["should_escalate"] is True


class TestDocumentationNode:
    """Tests for _documentation_node method."""

    def test_documentation_with_result(self, mock_llm_client):
        """Test documentation node with result in state."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "result": {
                "agent_type": "care_coordinator",
                "response": "Test response",
            },
            "should_escalate": False,
            "escalation_reason": "",
        }

        result = workflow._documentation_node(state)

        assert "documentation" in result
        assert result["documentation"]["agent_type"] == "care_coordinator"
        assert result["documentation"]["response"] == "Test response"
        assert result["documentation"]["escalated"] is False

    def test_documentation_with_escalation(self, mock_llm_client):
        """Test documentation node with escalation."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "result": {
                "agent_type": "nurse_triage",
                "response": "Escalating to nurse.",
            },
            "should_escalate": True,
            "escalation_reason": "Critical symptoms",
        }

        result = workflow._documentation_node(state)

        assert result["documentation"]["escalated"] is True
        assert result["documentation"]["escalation_reason"] == "Critical symptoms"

    def test_documentation_empty_result(self, mock_llm_client):
        """Test documentation node with empty result."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "result": {},
        }

        result = workflow._documentation_node(state)

        assert result["documentation"]["agent_type"] == "unknown"
        assert result["documentation"]["response"] == ""

    def test_documentation_preserves_state(self, mock_llm_client):
        """Test that documentation node preserves existing state."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "result": {"agent_type": "care_coordinator"},
            "extra_key": "extra_value",
            "message": "Test message",
        }

        result = workflow._documentation_node(state)

        assert result["extra_key"] == "extra_value"
        assert result["message"] == "Test message"


class TestEscalationNode:
    """Tests for _escalation_node method."""

    def test_escalation_node(self, mock_llm_client):
        """Test escalation node creates proper escalation result."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "message": "Critical issue",
            "escalation_reason": "Patient reported chest pain",
        }

        result = workflow._escalation_node(state)

        assert "result" in result
        assert result["result"]["agent_type"] == "escalation"
        assert result["result"]["escalate"] is True
        assert "connecting you with a nurse" in result["result"]["response"].lower()
        assert result["result"]["escalation_reason"] == "Patient reported chest pain"

    def test_escalation_node_default_reason(self, mock_llm_client):
        """Test escalation node with default reason."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "message": "Test",
        }

        result = workflow._escalation_node(state)

        assert result["result"]["escalation_reason"] == "Unknown"

    def test_escalation_node_preserves_state(self, mock_llm_client):
        """Test that escalation node preserves existing state."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "message": "Test",
            "extra_key": "extra_value",
            "context": {"patient": {"name": "John"}},
        }

        result = workflow._escalation_node(state)

        assert result["extra_key"] == "extra_value"
        assert result["context"]["patient"]["name"] == "John"


class TestProcessMessage:
    """Tests for process_message method."""

    @pytest.mark.asyncio
    async def test_process_message_success(self, mock_llm_client):
        """Test successful message processing through workflow."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "message": "Test message",
                "context": {},
                "routing": {"agent": "care_coordinator"},
                "result": {
                    "response": "I'm here to help!",
                    "agent_type": "care_coordinator",
                    "escalate": False,
                    "metadata": {"confidence": 0.9},
                },
                "should_escalate": False,
                "escalation_reason": "",
            }
        )

        with patch.object(workflow, "_get_workflow", return_value=mock_compiled):
            result = await workflow.process_message(
                message="Hello",
                context={"patient": {"name": "John"}},
            )

            assert result["response"] == "I'm here to help!"
            assert result["agent_type"] == "care_coordinator"
            assert result["escalate"] is False
            assert result["routing"]["agent"] == "care_coordinator"

    @pytest.mark.asyncio
    async def test_process_message_with_escalation(self, mock_llm_client):
        """Test message processing with escalation."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "message": "Critical issue",
                "context": {},
                "routing": {"agent": "nurse_triage"},
                "result": {
                    "response": "Connecting you with a nurse.",
                    "agent_type": "nurse_triage",
                    "escalate": True,
                },
                "should_escalate": True,
                "escalation_reason": "Critical symptoms",
            }
        )

        with patch.object(workflow, "_get_workflow", return_value=mock_compiled):
            result = await workflow.process_message(
                message="I have chest pain",
                context={},
            )

            assert result["escalate"] is True
            assert result["escalation_reason"] == "Critical symptoms"

    @pytest.mark.asyncio
    async def test_process_message_error_recovery(self, mock_llm_client):
        """Test message processing error recovery."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(side_effect=Exception("Workflow error"))

        with patch.object(workflow, "_get_workflow", return_value=mock_compiled):
            result = await workflow.process_message(
                message="Test",
                context={},
            )

            assert result["escalate"] is True
            assert "Workflow error" in result["escalation_reason"]
            assert result["agent_type"] == "error"

    @pytest.mark.asyncio
    async def test_process_message_missing_result(self, mock_llm_client):
        """Test message processing with missing result data."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "message": "Test",
                "context": {},
                "routing": {},
                "should_escalate": False,
            }
        )

        with patch.object(workflow, "_get_workflow", return_value=mock_compiled):
            result = await workflow.process_message(
                message="Test",
                context={},
            )

            assert result["response"] == ""
            assert result["agent_type"] == "unknown"

    @pytest.mark.asyncio
    async def test_process_message_workflow_invoked_with_correct_state(self, mock_llm_client):
        """Test that workflow is invoked with correct initial state."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "result": {"response": "Test", "agent_type": "care_coordinator"},
                "should_escalate": False,
                "routing": {},
            }
        )

        with patch.object(workflow, "_get_workflow", return_value=mock_compiled):
            await workflow.process_message(
                message="Hello",
                context={"patient": {"name": "John"}},
            )

            call_args = mock_compiled.ainvoke.call_args[0][0]
            assert call_args["message"] == "Hello"
            assert call_args["context"]["patient"]["name"] == "John"
            assert call_args["routing"] == {}
            assert call_args["result"] == {}
            assert call_args["should_escalate"] is False
            assert call_args["escalation_reason"] == ""


class TestGetWorkflowSingleton:
    """Tests for get_workflow singleton function."""

    def test_get_workflow_creates_instance(self):
        """Test that get_workflow creates a new instance."""
        reset_workflow()

        with patch("apps.agents.workflow.AgentWorkflow") as mock_workflow_class:
            mock_instance = Mock()
            mock_workflow_class.return_value = mock_instance

            result = get_workflow()

            assert result == mock_instance
            mock_workflow_class.assert_called_once()

    def test_get_workflow_returns_existing(self):
        """Test that get_workflow returns existing instance."""
        reset_workflow()

        with patch("apps.agents.workflow.AgentWorkflow") as mock_workflow_class:
            mock_instance = Mock()
            mock_workflow_class.return_value = mock_instance

            # First call
            result1 = get_workflow()
            # Second call should return same instance
            result2 = get_workflow()

            assert result1 == result2
            mock_workflow_class.assert_called_once()

    def test_get_workflow_after_reset(self):
        """Test that get_workflow creates new instance after reset."""
        reset_workflow()

        with patch("apps.agents.workflow.AgentWorkflow") as mock_workflow_class:
            mock_instance1 = Mock()
            mock_instance2 = Mock()
            mock_workflow_class.side_effect = [mock_instance1, mock_instance2]

            result1 = get_workflow()
            reset_workflow()
            result2 = get_workflow()

            assert result1 == mock_instance1
            assert result2 == mock_instance2
            assert result1 != result2
            assert mock_workflow_class.call_count == 2


class TestResetWorkflow:
    """Tests for reset_workflow function."""

    def test_reset_workflow_clears_instance(self):
        """Test that reset_workflow clears the singleton instance."""
        reset_workflow()

        with patch("apps.agents.workflow.AgentWorkflow") as mock_workflow_class:
            mock_instance = Mock()
            mock_workflow_class.return_value = mock_instance

            # Create instance
            get_workflow()
            # Reset
            reset_workflow()
            # Create new instance
            result = get_workflow()

            assert mock_workflow_class.call_count == 2

    def test_reset_workflow_when_none(self):
        """Test that reset_workflow works when no instance exists."""
        reset_workflow()

        # Should not raise
        reset_workflow()

        # Verify we can still create an instance
        with patch("apps.agents.workflow.AgentWorkflow") as mock_workflow_class:
            mock_instance = Mock()
            mock_workflow_class.return_value = mock_instance

            result = get_workflow()
            assert result == mock_instance


class TestIntegrationScenarios:
    """Integration tests for complete workflow scenarios."""

    @pytest.mark.asyncio
    async def test_full_workflow_care_coordinator_path(self, mock_llm_client):
        """Test complete workflow through care coordinator path."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        # Mock the compiled workflow
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "message": "When can I shower?",
                "context": {"patient": {"name": "John"}},
                "routing": {"agent": "care_coordinator", "urgency": "routine"},
                "result": {
                    "response": "You can shower after 48 hours.",
                    "agent_type": "care_coordinator",
                    "escalate": False,
                    "metadata": {"confidence": 0.9},
                },
                "should_escalate": False,
                "escalation_reason": "",
                "documentation": {
                    "agent_type": "care_coordinator",
                    "response": "You can shower after 48 hours.",
                    "escalated": False,
                },
            }
        )

        with patch.object(workflow, "_get_workflow", return_value=mock_compiled):
            result = await workflow.process_message(
                message="When can I shower?",
                context={"patient": {"name": "John"}},
            )

            assert result["response"] == "You can shower after 48 hours."
            assert result["agent_type"] == "care_coordinator"
            assert result["escalate"] is False

    @pytest.mark.asyncio
    async def test_full_workflow_nurse_triage_path(self, mock_llm_client):
        """Test complete workflow through nurse triage path."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "message": "I have pain around my incision",
                "context": {},
                "routing": {"agent": "nurse_triage", "urgency": "urgent"},
                "result": {
                    "response": "Some pain is normal. Monitor for increased redness.",
                    "agent_type": "nurse_triage",
                    "escalate": False,
                },
                "should_escalate": False,
                "escalation_reason": "",
            }
        )

        with patch.object(workflow, "_get_workflow", return_value=mock_compiled):
            result = await workflow.process_message(
                message="I have pain around my incision",
                context={},
            )

            assert result["agent_type"] == "nurse_triage"
            assert result["escalate"] is False

    @pytest.mark.asyncio
    async def test_full_workflow_escalation_path(self, mock_llm_client):
        """Test complete workflow through escalation path."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "message": "I have severe chest pain",
                "context": {},
                "routing": {"agent": "nurse_triage"},
                "result": {
                    "response": "I'm connecting you with a nurse right away.",
                    "agent_type": "escalation",
                    "escalate": True,
                },
                "should_escalate": True,
                "escalation_reason": "Critical symptom: chest pain",
            }
        )

        with patch.object(workflow, "_get_workflow", return_value=mock_compiled):
            result = await workflow.process_message(
                message="I have severe chest pain",
                context={},
            )

            assert result["escalate"] is True
            assert "chest pain" in result["escalation_reason"].lower()

    @pytest.mark.asyncio
    async def test_full_workflow_specialist_path(self, mock_llm_client):
        """Test complete workflow through specialist path."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "message": "I need help with my diet",
                "context": {},
                "routing": {"agent": "specialist_nutrition"},
                "target_specialist": "specialist_nutrition",
                "result": {
                    "response": "I'll connect you with our nutrition team.",
                    "agent_type": "specialist_nutrition",
                    "escalate": True,
                },
                "should_escalate": True,
                "escalation_reason": "Routed to specialist_nutrition",
            }
        )

        with patch.object(workflow, "_get_workflow", return_value=mock_compiled):
            result = await workflow.process_message(
                message="I need help with my diet",
                context={},
            )

            assert result["escalate"] is True
            assert "nutrition" in result["escalation_reason"].lower()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_message(self, mock_llm_client):
        """Test workflow with empty message."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        # Should not raise
        assert workflow is not None

    def test_empty_context(self, mock_llm_client):
        """Test workflow with empty context."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        # Should not raise
        assert workflow is not None

    def test_none_values_in_state(self, mock_llm_client):
        """Test nodes handle None values in state."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        state = {
            "message": None,
            "context": None,
            "routing": None,
        }

        # Should not raise
        result = workflow._route_from_supervisor({"routing": {}, "should_escalate": False})
        assert result == "care_coordinator"

    @pytest.mark.asyncio
    async def test_concurrent_workflow_access(self, mock_llm_client):
        """Test that workflow handles concurrent access properly."""
        import asyncio

        workflow = AgentWorkflow(llm_client=mock_llm_client)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "result": {"response": "Test", "agent_type": "care_coordinator"},
                "should_escalate": False,
                "routing": {},
            }
        )

        with patch.object(workflow, "_get_workflow", return_value=mock_compiled):
            # Process multiple messages concurrently
            tasks = [workflow.process_message(f"Message {i}", {}) for i in range(5)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            for result in results:
                assert result["response"] == "Test"

    def test_specialist_dict_keys(self, mock_llm_client):
        """Test that all specialist keys are valid."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        expected_specialists = {
            "specialist_cardiology",
            "specialist_social_work",
            "specialist_nutrition",
            "specialist_pt_rehab",
            "specialist_palliative",
            "specialist_pharmacy",
        }

        assert set(workflow.specialists.keys()) == expected_specialists

    @pytest.mark.asyncio
    async def test_node_handles_missing_keys_gracefully(self, mock_llm_client):
        """Test that nodes handle missing state keys gracefully."""
        workflow = AgentWorkflow(llm_client=mock_llm_client)

        # Test with completely empty state
        empty_state = {}

        # _route_from_supervisor should handle missing keys
        result = workflow._route_from_supervisor({"should_escalate": False})
        assert result == "care_coordinator"

        # _documentation_node should handle missing keys
        result = workflow._documentation_node(empty_state)
        assert "documentation" in result
        assert result["documentation"]["agent_type"] == "unknown"

        # _escalation_node should handle missing keys
        result = workflow._escalation_node(empty_state)
        assert "result" in result
        assert result["result"]["escalation_reason"] == "Unknown"
