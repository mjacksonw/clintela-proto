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
from apps.pathways.models import PathwayMilestone, PatientMilestoneCheckin
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
def send_proactive_checkin(patient_id: str, milestone_id: int):
    """Send proactive check-in based on pathway milestone.

    Args:
        patient_id: Patient UUID
        milestone_id: PathwayMilestone ID

    Returns:
        Dict with result
    """
    try:
        patient = Patient.objects.get(id=patient_id)
        milestone = PathwayMilestone.objects.get(id=milestone_id)
    except (Patient.DoesNotExist, PathwayMilestone.DoesNotExist) as e:
        logger.error(f"Failed to get patient or milestone: {e}")
        return {"error": "Patient or milestone not found"}

    try:
        # Get or create check-in record
        checkin, created = PatientMilestoneCheckin.objects.get_or_create(
            patient=patient,
            milestone=milestone,
            defaults={"sent_at": timezone.now()},
        )

        if not created and checkin.sent_at:
            logger.info(f"Check-in already sent for patient {patient_id}, milestone {milestone_id}")
            return {"success": False, "reason": "Already sent"}

        # Build check-in message
        questions = milestone.check_in_questions
        first_name = patient.user.first_name if patient.user else "Patient"
        if questions:
            message = f"Hi {first_name}! It's day {milestone.day} of your recovery. {questions[0]}"
        else:
            message = f"Hi {first_name}! How are you feeling on day {milestone.day} of your recovery?"

        # Get or create conversation
        conversation = ConversationService.get_or_create_conversation(
            patient,
            agent_type="care_coordinator",
        )

        # Add system message
        ConversationService.add_message(
            conversation=conversation,
            role="assistant",
            content=message,
            agent_type="care_coordinator",
            metadata={
                "proactive": True,
                "milestone_day": milestone.day,
                "milestone_title": milestone.title,
            },
        )

        # Update check-in record
        checkin.sent_at = timezone.now()
        checkin.save()

        logger.info(f"Sent proactive check-in to patient {patient_id} for milestone {milestone_id}")

        return {
            "success": True,
            "message": message,
            "milestone_day": milestone.day,
        }

    except Exception as e:
        logger.error(f"Failed to send proactive check-in: {e}")
        return {"error": str(e)}


@shared_task
def check_missed_checkins():
    """Check for missed check-ins and alert clinicians.

    This task runs periodically to identify patients who haven't
    responded to proactive check-ins.

    Returns:
        Dict with count of missed check-ins
    """
    from apps.agents.services import EscalationService

    # Find check-ins sent 24+ hours ago with no response
    cutoff_time = timezone.now() - timedelta(hours=24)

    missed_checkins = PatientMilestoneCheckin.objects.filter(
        sent_at__lte=cutoff_time,
        completed_at__isnull=True,
        skipped=False,
    ).select_related("patient", "milestone")

    count = 0
    for checkin in missed_checkins:
        try:
            # Create escalation for missed check-in
            EscalationService.create_escalation(
                patient=checkin.patient,
                conversation=None,
                reason=f"Missed check-in for day {checkin.milestone.day}: {checkin.milestone.title}",
                severity="routine",
                conversation_summary=f"Patient did not respond to proactive check-in sent {checkin.sent_at}",
                patient_context={
                    "milestone_day": checkin.milestone.day,
                    "milestone_title": checkin.milestone.title,
                },
            )

            # Mark as alerted
            checkin.notes = f"Escalated on {timezone.now().isoformat()}"
            checkin.save()

            count += 1

        except Exception as e:
            logger.error(f"Failed to escalate missed check-in {checkin.id}: {e}")

    logger.info(f"Escalated {count} missed check-ins")

    return {"missed_checkins": count}


@shared_task
def schedule_proactive_checkins():
    """Schedule proactive check-ins for patients based on their pathway.

    This task runs daily to schedule check-ins for patients
    who have reached a new milestone.

    Returns:
        Dict with count of scheduled check-ins
    """
    from apps.pathways.models import PatientPathway

    # Get all active patient pathways
    active_pathways = PatientPathway.objects.filter(
        status="active",
    ).select_related("patient", "pathway")

    scheduled = 0
    for patient_pathway in active_pathways:
        try:
            patient = patient_pathway.patient
            days_post_op = patient.days_post_op()

            # Find milestone for current day
            milestone = PathwayMilestone.objects.filter(
                pathway=patient_pathway.pathway,
                day=days_post_op,
                is_active=True,
            ).first()

            if not milestone:
                continue

            # Check if check-in already exists
            existing = PatientMilestoneCheckin.objects.filter(
                patient=patient,
                milestone=milestone,
            ).exists()

            if existing:
                continue

            # Schedule check-in (send immediately or delay based on preference)
            send_proactive_checkin.delay(
                patient_id=str(patient.id),
                milestone_id=milestone.id,
            )

            scheduled += 1

        except Exception as e:
            logger.error(f"Failed to schedule check-in for patient {patient_pathway.patient_id}: {e}")

    logger.info(f"Scheduled {scheduled} proactive check-ins")

    return {"scheduled": scheduled}


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
                        "outcome": conversation.escalation_reason or "Completed",
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
