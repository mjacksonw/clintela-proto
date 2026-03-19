"""Services for agent conversation management."""

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.agents.models import AgentConversation, AgentMessage, ConversationState
from apps.patients.models import Patient

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing agent conversations."""

    @staticmethod
    @transaction.atomic
    def get_or_create_conversation(
        patient: Patient,
        agent_type: str = "supervisor",
    ) -> AgentConversation:
        """Get existing active conversation or create new one.

        Args:
            patient: Patient instance
            agent_type: Type of agent for this conversation

        Returns:
            AgentConversation instance
        """
        # Look for active conversation with lock
        conversation = (
            AgentConversation.objects.filter(
                patient=patient,
                status="active",
            )
            .select_for_update()
            .first()
        )

        if conversation:
            return conversation

        # Create new conversation
        conversation = AgentConversation.objects.create(
            patient=patient,
            agent_type=agent_type,
            status="active",
            context={},
        )

        # Create initial state
        ConversationState.objects.create(
            conversation=conversation,
            patient_summary=f"{patient.user.first_name} {patient.user.last_name}",
        )

        return conversation

    @staticmethod
    def add_message(
        conversation: AgentConversation,
        role: str,
        content: str,
        agent_type: str = "",
        routing_decision: str = "",
        confidence_score: float | None = None,
        escalation_triggered: bool = False,
        escalation_reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AgentMessage:
        """Add a message to the conversation.

        Args:
            conversation: AgentConversation instance
            role: 'user' or 'assistant'
            content: Message content
            agent_type: Type of agent that generated response
            routing_decision: Routing decision from supervisor
            confidence_score: Confidence score
            escalation_triggered: Whether escalation was triggered
            escalation_reason: Reason for escalation
            metadata: Additional metadata

        Returns:
            Created AgentMessage
        """
        return AgentMessage.objects.create(
            conversation=conversation,
            role=role,
            content=content,
            agent_type=agent_type,
            routing_decision=routing_decision,
            confidence_score=confidence_score,
            escalation_triggered=escalation_triggered,
            escalation_reason=escalation_reason,
            metadata=metadata or {},
        )

    @staticmethod
    def get_conversation_history(
        conversation: AgentConversation,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get recent conversation history.

        Args:
            conversation: AgentConversation instance
            limit: Number of messages to return

        Returns:
            List of message dicts
        """
        messages = AgentMessage.objects.filter(
            conversation=conversation,
        ).order_by("-created_at")[:limit]

        return [
            {
                "role": msg.role,
                "content": msg.content,
                "agent_type": msg.agent_type,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in reversed(messages)  # Oldest first
        ]

    @staticmethod
    def update_conversation_status(
        conversation: AgentConversation,
        status: str,
        escalation_reason: str = "",
    ) -> None:
        """Update conversation status.

        Args:
            conversation: AgentConversation instance
            status: New status
            escalation_reason: Reason for escalation (if applicable)
        """
        conversation.status = status
        if escalation_reason:
            conversation.escalation_reason = escalation_reason
        conversation.save()

    @staticmethod
    def update_context(
        conversation: AgentConversation,
        context_updates: dict[str, Any],
    ) -> None:
        """Update conversation context.

        Args:
            conversation: AgentConversation instance
            context_updates: Dict of updates to merge into context
        """
        conversation.context.update(context_updates)
        conversation.save()

    @staticmethod
    def add_tool_invocation(
        conversation: AgentConversation,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: dict[str, Any],
    ) -> None:
        """Record a tool invocation.

        Args:
            conversation: AgentConversation instance
            tool_name: Name of the tool
            tool_input: Tool input parameters
            tool_output: Tool output
        """
        invocation = {
            "tool": tool_name,
            "input": tool_input,
            "output": tool_output,
            "timestamp": timezone.now().isoformat(),
        }
        conversation.tool_invocations.append(invocation)
        conversation.save()


class ContextService:
    """Service for assembling conversation context."""

    @staticmethod
    def get_patient_context(patient: Patient) -> dict[str, Any]:
        """Get patient context for agent.

        Args:
            patient: Patient instance

        Returns:
            Patient context dict
        """
        # Get active pathway if any
        active_pathway = (
            patient.pathways.filter(
                status="active",
            )
            .select_related("pathway")
            .first()
        )

        context = {
            "id": str(patient.id),
            "name": f"{patient.user.first_name} {patient.user.last_name}",
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "surgery_type": patient.surgery_type or "Unknown",
            "surgery_date": patient.surgery_date.isoformat() if patient.surgery_date else None,
            "days_post_op": patient.days_post_op(),
            "status": patient.status,
            "phone": str(patient.user.phone_number) if patient.user.phone_number else None,
        }

        if active_pathway:
            context["pathway"] = {
                "name": active_pathway.pathway.name,
                "surgery_type": active_pathway.pathway.surgery_type,
                "started_at": active_pathway.started_at.isoformat(),
            }

        return context

    @staticmethod
    def get_pathway_context(patient: Patient) -> dict[str, Any]:
        """Get pathway context for agent.

        Args:
            patient: Patient instance

        Returns:
            Pathway context dict
        """
        from apps.pathways.models import PathwayMilestone

        active_pathway = (
            patient.pathways.filter(
                status="active",
            )
            .select_related("pathway")
            .first()
        )

        if not active_pathway:
            return {
                "current_phase": "unknown",
                "milestones": [],
            }

        days_post_op = patient.days_post_op()

        # Get current milestone
        current_milestone = (
            PathwayMilestone.objects.filter(
                pathway=active_pathway.pathway,
                day__lte=days_post_op,
                is_active=True,
            )
            .order_by("-day")
            .first()
        )

        # Get next milestone
        next_milestone = (
            PathwayMilestone.objects.filter(
                pathway=active_pathway.pathway,
                day__gt=days_post_op,
                is_active=True,
            )
            .order_by("day")
            .first()
        )

        return {
            "current_phase": current_milestone.phase if current_milestone else "unknown",
            "current_milestone": {
                "day": current_milestone.day,
                "title": current_milestone.title,
                "expected_symptoms": current_milestone.expected_symptoms,
                "activities": current_milestone.activities,
                "red_flags": current_milestone.red_flags,
            }
            if current_milestone
            else None,
            "next_milestone": {
                "day": next_milestone.day,
                "title": next_milestone.title,
            }
            if next_milestone
            else None,
        }

    @staticmethod
    def get_recent_symptoms(conversation: AgentConversation) -> list[str]:
        """Extract recent symptoms from conversation.

        Args:
            conversation: AgentConversation instance

        Returns:
            List of recent symptoms
        """
        # This is a simplified version - in production, you'd use NLP
        # to extract symptoms from messages
        recent_messages = AgentMessage.objects.filter(
            conversation=conversation,
            role="user",
        ).order_by("-created_at")[:5]

        symptoms = []
        symptom_keywords = [
            "pain",
            "fever",
            "nausea",
            "vomiting",
            "bleeding",
            "swelling",
            "redness",
            "discharge",
            "dizziness",
            "fatigue",
            "tired",
            "weakness",
            "appetite",
        ]

        for msg in recent_messages:
            content_lower = msg.content.lower()
            for keyword in symptom_keywords:
                if keyword in content_lower:
                    # Extract sentence containing symptom
                    sentences = msg.content.split(".")
                    for sentence in sentences:
                        if keyword in sentence.lower():
                            symptoms.append(sentence.strip())
                            break

        return list(set(symptoms))[:5]  # Deduplicate and limit

    @staticmethod
    def assemble_full_context(
        patient: Patient,
        conversation: AgentConversation | None = None,
    ) -> dict[str, Any]:
        """Assemble full context for agent.

        Args:
            patient: Patient instance
            conversation: Optional conversation instance

        Returns:
            Full context dict
        """
        context = {
            "patient": ContextService.get_patient_context(patient),
            "pathway": ContextService.get_pathway_context(patient),
        }

        if conversation:
            context["conversation_history"] = ConversationService.get_conversation_history(
                conversation,
                limit=10,
            )
            context["recent_symptoms"] = ContextService.get_recent_symptoms(conversation)

            # Get conversation state
            try:
                state = conversation.state
                context["state"] = {
                    "patient_summary": state.patient_summary,
                    "recovery_phase": state.recovery_phase,
                    "medications": state.medications,
                }
            except ConversationState.DoesNotExist:
                pass

        return context


class EscalationService:
    """Service for handling escalations to human clinicians."""

    @staticmethod
    @transaction.atomic
    def create_escalation(
        patient: Patient,
        conversation: AgentConversation | None,
        reason: str,
        severity: str,
        conversation_summary: str = "",
        patient_context: dict[str, Any] | None = None,
    ):
        """Create a new escalation.

        Args:
            patient: Patient instance
            conversation: Optional conversation that triggered escalation
            reason: Reason for escalation
            severity: 'critical', 'urgent', or 'routine'
            conversation_summary: Summary of conversation
            patient_context: Patient context dict

        Returns:
            Created Escalation instance
        """
        from apps.agents.models import Escalation

        escalation = Escalation.objects.create(
            patient=patient,
            conversation=conversation,
            reason=reason,
            severity=severity,
            conversation_summary=conversation_summary,
            patient_context=patient_context or {},
            status="pending",
        )

        # Update conversation status if provided
        if conversation:
            conversation.status = "escalated"
            conversation.escalation_reason = reason
            conversation.save()

        logger.info(f"Created escalation {escalation.id} for patient {patient.id}")

        return escalation

    @staticmethod
    def acknowledge_escalation(
        escalation_id: str,
        clinician_id: int,
    ) -> bool:
        """Acknowledge an escalation.

        Args:
            escalation_id: Escalation UUID
            clinician_id: ID of acknowledging clinician

        Returns:
            True if successful
        """
        from apps.accounts.models import User
        from apps.agents.models import Escalation

        try:
            escalation = Escalation.objects.get(id=escalation_id)
            clinician = User.objects.get(id=clinician_id)

            escalation.status = "acknowledged"
            escalation.assigned_to = clinician
            escalation.acknowledged_at = timezone.now()
            escalation.save()

            logger.info(f"Escalation {escalation_id} acknowledged by {clinician_id}")
            return True
        except (Escalation.DoesNotExist, User.DoesNotExist):
            return False

    @staticmethod
    def resolve_escalation(
        escalation_id: str,
        resolution_notes: str = "",
    ) -> bool:
        """Resolve an escalation.

        Args:
            escalation_id: Escalation UUID
            resolution_notes: Notes about resolution

        Returns:
            True if successful
        """
        from apps.agents.models import Escalation

        try:
            escalation = Escalation.objects.get(id=escalation_id)
            escalation.status = "resolved"
            escalation.resolved_at = timezone.now()
            escalation.save()

            # Update patient status if needed
            if escalation.conversation:
                escalation.conversation.status = "completed"
                escalation.conversation.save()

            logger.info(f"Escalation {escalation_id} resolved")
            return True
        except Escalation.DoesNotExist:
            return False

    @staticmethod
    def get_pending_escalations(hospital_id: int | None = None):
        """Get pending escalations.

        Args:
            hospital_id: Optional hospital filter

        Returns:
            QuerySet of pending escalations
        """
        from apps.agents.models import Escalation

        queryset = Escalation.objects.filter(
            status="pending",
        ).select_related("patient", "conversation")

        if hospital_id:
            queryset = queryset.filter(patient__hospital_id=hospital_id)

        return queryset.order_by("-created_at")

    @staticmethod
    def generate_conversation_summary(
        conversation: AgentConversation,
    ) -> str:
        """Generate a summary of the conversation for escalation.

        Args:
            conversation: AgentConversation instance

        Returns:
            Summary string
        """
        messages = AgentMessage.objects.filter(
            conversation=conversation,
        ).order_by("created_at")

        if not messages.exists():
            return "No messages in conversation."

        lines = []
        for msg in messages:
            role = "Patient" if msg.role == "user" else "AI"
            lines.append(f"{role}: {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}")

        return "\n".join(lines)

    @staticmethod
    def generate_handoff_notes(
        conversation: AgentConversation,
        escalation_reason: str,
    ) -> str:
        """Generate handoff notes for human clinician.

        Args:
            conversation: AgentConversation instance
            escalation_reason: Reason for escalation

        Returns:
            Handoff notes string
        """
        patient = conversation.patient
        summary = EscalationService.generate_conversation_summary(conversation)

        # Get AI messages to understand what was covered
        ai_messages = AgentMessage.objects.filter(
            conversation=conversation,
            role="assistant",
        ).order_by("created_at")

        ai_coverage = []
        for msg in ai_messages:
            if msg.agent_type:
                ai_coverage.append(f"- {msg.agent_type}: {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}")

        # Get escalation history
        escalations = conversation.escalations.all().order_by("-created_at")
        escalation_history = []
        for esc in escalations[:3]:  # Last 3 escalations
            escalation_history.append(f"- {esc.created_at.strftime('%Y-%m-%d')}: {esc.reason[:80]}")

        notes = f"""## AI Handoff Notes
**Patient:** {patient.user.first_name} {patient.user.last_name} | **Escalated:** {conversation.updated_at.isoformat()}

### Conversation Summary
{summary[:500]}{'...' if len(summary) > 500 else ''}

### Escalation Trigger
{escalation_reason}

### Patient Context
- Surgery: {patient.surgery_type or 'Unknown'}
- Days Post-Op: {patient.days_post_op()}
- Status: {patient.status}
- Phone: {patient.user.phone_number if patient.user.phone_number else 'N/A'}

### What AI Covered
{chr(10).join(ai_coverage) if ai_coverage else "- No AI responses recorded"}

### Recent Escalation History
{chr(10).join(escalation_history) if escalation_history else "- No previous escalations"}

### AI Agent History
- Primary Agent: {conversation.agent_type}
- Tools Used: {len(conversation.tool_invocations)} invocations
- Confidence Scores: {', '.join([str(m.confidence_score) for m in ai_messages if m.confidence_score]) or 'N/A'}

### Suggested Next Steps
1. Review patient's current status and symptoms
2. Verify AI assessment aligns with clinical judgment
3. Follow up on any outstanding concerns
4. Update care plan if needed
"""

        return notes

    @staticmethod
    def generate_structured_handoff(
        conversation: AgentConversation,
        escalation_reason: str,
    ) -> dict[str, Any]:
        """Generate structured handoff data for clinician dashboard.

        Args:
            conversation: AgentConversation instance
            escalation_reason: Reason for escalation

        Returns:
            Dict with structured handoff data
        """
        patient = conversation.patient

        # Get messages
        messages = AgentMessage.objects.filter(
            conversation=conversation,
        ).order_by("created_at")

        # Build conversation timeline
        timeline = []
        for msg in messages:
            timeline.append(
                {
                    "timestamp": msg.created_at.isoformat(),
                    "role": msg.role,
                    "agent_type": msg.agent_type,
                    "content": msg.content[:200] + ("..." if len(msg.content) > 200 else ""),
                    "confidence": msg.confidence_score,
                    "escalation_triggered": msg.escalation_triggered,
                }
            )

        # Get patient context
        context = ContextService.get_patient_context(patient)

        return {
            "patient": {
                "id": str(patient.id),
                "name": f"{patient.user.first_name} {patient.user.last_name}",
                "surgery_type": patient.surgery_type,
                "days_post_op": patient.days_post_op(),
                "status": patient.status,
                "phone": str(patient.user.phone_number) if patient.user.phone_number else None,
            },
            "escalation": {
                "reason": escalation_reason,
                "timestamp": conversation.updated_at.isoformat(),
                "severity": "critical" if "critical" in escalation_reason.lower() else "urgent",
            },
            "conversation": {
                "id": str(conversation.id),
                "agent_type": conversation.agent_type,
                "duration_minutes": (conversation.updated_at - conversation.created_at).total_seconds() / 60,
                "message_count": messages.count(),
            },
            "timeline": timeline,
            "context": context,
            "ai_coverage": EscalationService.generate_conversation_summary(conversation),
        }
