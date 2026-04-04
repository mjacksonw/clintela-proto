"""Celery tasks for agent system."""

import logging
from datetime import timedelta

try:
    from celery import shared_task

    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

    # Create a dummy decorator for when Celery is not installed
    def shared_task(*args, bind=False, **kwargs):
        # Check if decorator was called with just the function (no parentheses)
        if len(args) == 1 and callable(args[0]) and not kwargs and not bind:
            # @shared_task without parentheses - args[0] is the function
            func = args[0]
            # Return the wrapped function directly
            func.delay = func
            return func

        def decorator(func):
            # Store original function
            original_func = func

            # For bind=True tasks, the first arg is 'self' (the task instance)
            # In both cases, just use the function directly
            wrapped_func = func

            # Attach .delay method that calls the wrapped function directly
            def delay(*d_args, **d_kwargs):
                return wrapped_func(*d_args, **d_kwargs)

            # Replace the function with a callable that accepts both direct calls and .delay
            def task_wrapper(*tw_args, **tw_kwargs):
                return wrapped_func(*tw_args, **tw_kwargs)

            task_wrapper.delay = delay
            task_wrapper.__name__ = original_func.__name__
            task_wrapper.__doc__ = original_func.__doc__
            task_wrapper._is_task = True
            task_wrapper._bind = bind

            return task_wrapper

        return decorator


from django.utils import timezone

from apps.agents.models import AgentConversation, AgentMessage
from apps.agents.services import ContextService, ConversationService
from apps.agents.workflow import get_workflow
from apps.patients.models import Patient

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_patient_message(self, patient_id: str, message: str):
    """Process patient message through agent workflow (async).

    Args:
        patient_id: Patient UUID
        message: Patient's message

    Returns:
        Dict with response and metadata
    """
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        logger.error(f"Patient {patient_id} not found")
        return {"error": "Patient not found"}

    try:
        # Get or create conversation
        conversation = ConversationService.get_or_create_conversation(patient)

        # Add user message
        ConversationService.add_message(
            conversation=conversation,
            role="user",
            content=message,
        )

        # Assemble context
        context = ContextService.assemble_full_context(patient, conversation)

        # Process through workflow (synchronously for Celery)
        import asyncio

        workflow = get_workflow()
        result = asyncio.run(workflow.process_message(message, context))

        # Add agent response
        ConversationService.add_message(
            conversation=conversation,
            role="assistant",
            content=result["response"],
            agent_type=result["agent_type"],
            confidence_score=result.get("metadata", {}).get("confidence"),
            escalation_triggered=result["escalate"],
            escalation_reason=result.get("escalation_reason", ""),
            metadata=result.get("metadata", {}),
        )

        # Handle escalation if needed
        if result["escalate"]:
            from apps.agents.services import EscalationService

            ConversationService.update_conversation_status(
                conversation=conversation,
                status="escalated",
                escalation_reason=result.get("escalation_reason", ""),
            )

            EscalationService.create_escalation(
                patient=patient,
                conversation=conversation,
                reason=result.get("escalation_reason", "Unknown"),
                severity=result.get("metadata", {}).get("severity", "urgent"),
                conversation_summary=result["response"],
                patient_context=context.get("patient", {}),
            )

        return {
            "success": True,
            "response": result["response"],
            "agent_type": result["agent_type"],
            "escalate": result["escalate"],
        }

    except Exception as e:
        logger.error(f"Failed to process message for patient {patient_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=2**self.request.retries) from None
        return {"error": str(e)}


@shared_task
def cleanup_old_conversations(days: int = 30):
    """Clean up old completed conversations.

    Args:
        days: Age in days to consider "old"

    Returns:
        Dict with count of cleaned conversations
    """
    cutoff_date = timezone.now() - timedelta(days=days)

    old_conversations = AgentConversation.objects.filter(
        status__in=["completed", "escalated"],
        updated_at__lt=cutoff_date,
    )

    count = old_conversations.count()
    old_conversations.delete()

    logger.info(f"Cleaned up {count} old conversations")

    return {"deleted": count}


@shared_task
def generate_conversation_summaries():
    """Generate summaries for completed conversations.

    This task runs periodically to generate documentation
    for conversations that don't have summaries yet.

    Returns:
        Dict with count of generated summaries
    """
    from apps.agents.agents import DocumentationAgent

    # Find conversations without summaries
    conversations = AgentConversation.objects.filter(
        status__in=["completed", "escalated"],
    ).select_related("patient")[:100]  # Process in batches

    generated = 0
    for conversation in conversations:
        try:
            # Get messages
            messages = AgentMessage.objects.filter(
                conversation=conversation,
            ).order_by("created_at")

            if not messages.exists():
                continue

            # Build transcript
            transcript_lines = []
            for msg in messages:
                role = "Patient" if msg.role == "user" else "AI"
                transcript_lines.append(f"{role}: {msg.content}")

            transcript = "\n".join(transcript_lines)

            # Generate documentation
            doc_agent = DocumentationAgent()
            import asyncio

            result = asyncio.run(
                doc_agent.process(
                    "",
                    {
                        "patient": {
                            "name": f"{conversation.patient.user.first_name} {conversation.patient.user.last_name}",
                        },
                        "transcript": transcript,
                        "actions": conversation.tool_invocations,
                        "outcome": "Completed",
                        "duration": str(conversation.updated_at - conversation.created_at),
                        "interaction_type": "Chat",
                    },
                )
            )

            # Store summary in conversation context
            conversation.context["summary"] = result.response
            conversation.save()

            generated += 1

        except Exception as e:
            logger.error(f"Failed to generate summary for conversation {conversation.id}: {e}")

    logger.info(f"Generated {generated} conversation summaries")

    return {"generated": generated}
