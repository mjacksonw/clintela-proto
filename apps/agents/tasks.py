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


from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from apps.agents.models import AgentConversation, AgentMessage
from apps.agents.services import ContextService, ConversationService
from apps.agents.workflow import get_workflow
from apps.pathways.models import PathwayMilestone, PatientMilestoneCheckin
from apps.patients.models import Patient

logger = logging.getLogger(__name__)


def _build_checkin_preamble(prefs, day):
    """Build a personalized check-in preamble from patient preferences.

    Uses simple template logic — not LLM-generated — to keep it
    genuine and predictable.
    """
    name = prefs.preferred_name or "there"

    # Early recovery (days 1-3): acknowledge difficulty
    if day <= 3:
        if prefs.living_situation and "alone" in prefs.living_situation.lower():
            return (
                f"Good morning {name} — I hope you had a restful night. "
                "I know the first few days home alone can be tough."
            )
        return f"Good morning {name} — I hope you're settling in. The first few days are often the hardest."

    # Active recovery (days 4-14): encourage progress
    if day <= 14:
        if prefs.recovery_goals:
            # Extract first goal phrase
            goal = prefs.recovery_goals.split(",")[0].split(".")[0].strip()
            return f"Hi {name} — you're making progress! Getting closer to {goal.lower()} every day."
        return f"Hi {name} — hope you're feeling a bit stronger today."

    # Established recovery (days 15+): celebrate milestones
    if prefs.recovery_goals:
        goal = prefs.recovery_goals.split(",")[0].split(".")[0].strip()
        return f"Hi {name} — day {day} already! How's the road back to {goal.lower()} going?"
    return f"Hi {name} — day {day}! You've come a long way."


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

        # Build check-in message with personalized preamble
        questions = milestone.check_in_questions
        first_name = patient.user.first_name if patient.user else "Patient"

        # Try to personalize with patient preferences
        preamble = ""
        try:
            prefs = patient.preferences
            if prefs.has_any_preferences:
                first_name = prefs.preferred_name or first_name
                preamble = _build_checkin_preamble(prefs, milestone.day)
        except ObjectDoesNotExist:
            logger.debug("No patient preferences for check-in personalization")

        if preamble and questions:
            message = f"{preamble} {questions[0]}"
        elif questions:
            message = f"Hi {first_name}! It's day {milestone.day} of your recovery. {questions[0]}"
        elif preamble:
            message = f"{preamble} How are you feeling today?"
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
    """Disabled: retain all conversation history for clinical and compliance reasons.

    Previously deleted conversations older than `days`. Now a no-op.
    """
    logger.info("cleanup_old_conversations is disabled (retain all history)")
    return {"deleted": 0}


@shared_task
def generate_conversation_summaries():
    """Generate summaries for completed conversations.

    This task runs periodically to generate documentation
    for conversations that don't have summaries yet.

    Returns:
        Dict with count of generated summaries
    """
    from apps.agents.agents import DocumentationAgent

    # Find care team conversations without summaries
    # (support group conversations get engagement summaries, not clinical docs)
    conversations = AgentConversation.objects.filter(
        status__in=["completed", "escalated"],
        conversation_type="care_team",
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


# =============================================================================
# Support Group Tasks
# =============================================================================


@shared_task(bind=True, max_retries=2)
def deliver_support_group_followup(  # noqa: C901
    self,
    conversation_id: str,
    persona_id: str,
    intent: str,
    generation_id: int,
    patient_context: dict,
):
    """Deliver a staggered followup response from a support group persona.

    Checks generation_id before executing. If the patient sent a new message
    since this task was scheduled, skip (stale).
    """
    from django.db import IntegrityError

    from apps.agents.llm_client import get_llm_client
    from apps.agents.personas import build_persona_prompt, get_persona

    try:
        conversation = AgentConversation.objects.get(id=conversation_id)
    except AgentConversation.DoesNotExist:
        logger.warning(f"Conversation {conversation_id} deleted, skipping followup")
        return {"skipped": True, "reason": "conversation_deleted"}

    # Staleness check
    if conversation.generation_id != generation_id:
        logger.info(f"Stale followup for {persona_id} (gen {generation_id} vs {conversation.generation_id})")
        return {"skipped": True, "reason": "stale_generation"}

    persona = get_persona(persona_id)
    if not persona:
        logger.warning(f"Unknown persona {persona_id}")
        return {"skipped": True, "reason": "unknown_persona"}

    # Build prompt and generate response
    memory = conversation.persona_memories.get(persona_id, "")
    prompt = build_persona_prompt(persona, patient_context, memory)

    # Get recent messages for context
    recent_messages = list(AgentMessage.objects.filter(conversation=conversation).order_by("-created_at")[:10])
    history = [{"role": m.role, "content": m.content, "persona_id": m.persona_id} for m in reversed(recent_messages)]

    # Get the patient's latest message
    patient_msg = next((m for m in reversed(history) if m["role"] == "user"), None)
    if not patient_msg:
        return {"skipped": True, "reason": "no_patient_message"}

    import asyncio

    llm = get_llm_client()
    messages = [{"role": "system", "content": prompt}]
    for msg in history:
        if msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
        else:
            name = msg.get("persona_id", "assistant")
            messages.append({"role": "assistant", "content": f"[{name}]: {msg['content']}"})
    messages.append(
        {
            "role": "system",
            "content": (
                f"Respond as a followup to the conversation. Intent: {intent}. "
                "Keep it to 1-3 sentences, warm and in character."
            ),
        }
    )
    messages.append({"role": "user", "content": patient_msg["content"]})

    from apps.agents.constants import LLM_MAX_TOKENS_SUPPORT_GROUP, LLM_TEMPERATURE_SUPPORT_GROUP

    try:
        result = asyncio.run(
            llm.generate(
                messages=messages,
                temperature=LLM_TEMPERATURE_SUPPORT_GROUP,
                max_tokens=LLM_MAX_TOKENS_SUPPORT_GROUP,
            )
        )
        content = result["content"].strip()
    except Exception as e:
        logger.error(f"Followup LLM failed for {persona_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=2**self.request.retries) from None
        return {"error": str(e)}

    # Save message (idempotency via UniqueConstraint)
    try:
        msg = AgentMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=content,
            persona_id=persona_id,
            generation_id=generation_id,
            metadata={"followup": True, "intent": intent},
        )
    except IntegrityError:
        logger.info(f"Duplicate followup for {persona_id} gen {generation_id}, skipping")
        return {"skipped": True, "reason": "duplicate"}

    # Push via WebSocket
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            f"support_group_{conversation.patient_id}",
            {
                "type": "support_group_message",
                "message_id": str(msg.id),
                "persona_id": persona.id,
                "persona_name": persona.name,
                "content": content,
                "avatar_color": persona.avatar_color,
                "avatar_color_dark": persona.avatar_color_dark,
                "avatar_initials": persona.avatar_initials,
            },
        )

    return {"success": True, "persona_id": persona_id}


@shared_task
def deliver_support_group_reaction(
    message_id: str,
    persona_id: str,
    emoji: str,
    generation_id: int,
):
    """Deliver an emoji reaction from a persona on a message."""
    from django.db import IntegrityError

    from apps.agents.models import SupportGroupReaction

    try:
        message = AgentMessage.objects.select_related("conversation").get(id=message_id)
    except AgentMessage.DoesNotExist:
        return {"skipped": True, "reason": "message_deleted"}

    # Staleness check
    if message.conversation.generation_id != generation_id:
        return {"skipped": True, "reason": "stale_generation"}

    try:
        SupportGroupReaction.objects.create(
            message=message,
            persona_id=persona_id,
            emoji=emoji,
        )
    except IntegrityError:
        return {"skipped": True, "reason": "duplicate"}

    # Push via WebSocket
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            f"support_group_{message.conversation.patient_id}",
            {
                "type": "support_group_reaction",
                "message_id": str(message.id),
                "persona_id": persona_id,
                "emoji": emoji,
            },
        )

    return {"success": True}


@shared_task
def summarize_persona_memory(conversation_id: str):
    """Summarize persona memories after every N messages.

    Also generates the clinician engagement summary (piggyback).
    Uses select_for_update to prevent concurrent write races.
    """
    from django.db import transaction

    from apps.agents.constants import SG_MEMORY_TOKEN_BUDGET
    from apps.agents.llm_client import get_llm_client
    from apps.agents.personas import PERSONA_REGISTRY
    from apps.agents.prompts import ENGAGEMENT_SUMMARY_PROMPT, MEMORY_SUMMARIZATION_PROMPT

    try:
        with transaction.atomic():
            conversation = AgentConversation.objects.select_for_update().get(id=conversation_id)

            recent_messages = list(AgentMessage.objects.filter(conversation=conversation).order_by("-created_at")[:20])
            if not recent_messages:
                return {"skipped": True}

            recent_text = "\n".join(
                f"{'Patient' if m.role == 'user' else (m.persona_id or 'AI')}: {m.content}"
                for m in reversed(recent_messages)
            )

            import asyncio

            llm = get_llm_client()
            memories = dict(conversation.persona_memories)

            # Summarize for each persona that participated
            active_personas = {m.persona_id for m in recent_messages if m.persona_id}
            for pid in active_personas:
                if pid not in PERSONA_REGISTRY:
                    continue
                persona = PERSONA_REGISTRY[pid]
                current_memory = memories.get(pid, "")

                prompt = MEMORY_SUMMARIZATION_PROMPT.format(
                    persona_name=persona.name,
                    current_memory=current_memory or "(none)",
                    recent_messages=recent_text,
                )

                try:
                    result = asyncio.run(
                        llm.generate(
                            messages=[{"role": "system", "content": prompt}],
                            temperature=0.3,
                            max_tokens=SG_MEMORY_TOKEN_BUDGET,
                        )
                    )
                    memories[pid] = result["content"].strip()
                except Exception as e:
                    logger.warning(f"Memory summarization failed for {pid}: {e}")
                    # Non-blocking: keep stale memory

            conversation.persona_memories = memories

            # Also generate clinician engagement summary (piggyback)
            try:
                summary_prompt = ENGAGEMENT_SUMMARY_PROMPT.format(recent_messages=recent_text)
                result = asyncio.run(
                    llm.generate(
                        messages=[{"role": "system", "content": summary_prompt}],
                        temperature=0.3,
                        max_tokens=200,
                    )
                )
                context = dict(conversation.context)
                context["engagement_summary"] = result["content"].strip()
                conversation.context = context
            except Exception as e:
                logger.warning(f"Engagement summary failed: {e}")

            conversation.save(update_fields=["persona_memories", "context"])
    except AgentConversation.DoesNotExist:
        return {"skipped": True}

    return {"success": True, "personas_updated": list(active_personas)}


@shared_task(bind=True, max_retries=3)
def send_weekly_group_prompt(self, patient_id: str):
    """Send a weekly group prompt from a rotating persona."""

    from apps.agents.personas import PERSONA_REGISTRY

    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return {"error": "Patient not found"}

    # Get support group conversation (must exist = patient has engaged)
    conversation = AgentConversation.objects.filter(
        patient=patient,
        conversation_type="support_group",
        status="active",
    ).first()

    if not conversation:
        return {"skipped": True, "reason": "no_conversation"}

    # Engagement gate: check patient has sent at least 1 message
    has_messages = AgentMessage.objects.filter(
        conversation=conversation,
        role="user",
    ).exists()
    if not has_messages:
        return {"skipped": True, "reason": "not_engaged"}

    # Rotate persona by week number
    week_num = timezone.now().isocalendar()[1]
    persona_ids = list(PERSONA_REGISTRY.keys())
    idx = week_num % len(persona_ids)
    persona = PERSONA_REGISTRY[persona_ids[idx]]

    # Create the prompt message
    try:
        msg = AgentMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=persona.weekly_prompt,
            persona_id=persona.id,
            metadata={"weekly_prompt": True, "week": week_num},
        )

        # Push via WebSocket
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"support_group_{patient_id}",
                {
                    "type": "support_group_message",
                    "message_id": str(msg.id),
                    "persona_id": persona.id,
                    "persona_name": persona.name,
                    "content": persona.weekly_prompt,
                    "avatar_color": persona.avatar_color,
                    "avatar_color_dark": persona.avatar_color_dark,
                    "avatar_initials": persona.avatar_initials,
                },
            )

        return {"success": True, "persona": persona.id}

    except Exception as e:
        logger.error(f"Weekly prompt failed for {patient_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=2**self.request.retries) from None
        return {"error": str(e)}


@shared_task(bind=True, max_retries=3)
def check_support_group_absence(self, patient_id: str):  # noqa: C901
    """Check if patient has been absent from support group and send Maria check-in."""
    from apps.agents.constants import SG_ABSENCE_THRESHOLD_DAYS
    from apps.agents.personas import PERSONA_REGISTRY

    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return {"error": "Patient not found"}

    conversation = AgentConversation.objects.filter(
        patient=patient,
        conversation_type="support_group",
        status="active",
    ).first()

    if not conversation:
        return {"skipped": True, "reason": "no_conversation"}

    # Engagement gate: must have sent at least 1 message
    last_user_msg = AgentMessage.objects.filter(conversation=conversation, role="user").order_by("-created_at").first()
    if not last_user_msg:
        return {"skipped": True, "reason": "not_engaged"}

    # Check if patient has been absent
    days_since = (timezone.now() - last_user_msg.created_at).days
    if days_since < SG_ABSENCE_THRESHOLD_DAYS:
        return {"skipped": True, "reason": "recent_activity"}

    # Check if we already sent a check-in since their last message
    existing_checkin = AgentMessage.objects.filter(
        conversation=conversation,
        persona_id="maria",
        metadata__absence_checkin=True,
        created_at__gt=last_user_msg.created_at,
    ).exists()
    if existing_checkin:
        return {"skipped": True, "reason": "already_checked_in"}

    # Maria sends a warm check-in
    maria = PERSONA_REGISTRY["maria"]
    name = patient.user.first_name if patient.user else "there"

    try:
        prefs = patient.preferences
        if prefs.preferred_name:
            name = prefs.preferred_name
    except Exception:  # noqa: BLE001
        logger.debug("Could not get preferred name for patient %s", patient_id)

    content = f"Hey {name}, just checking in. The group has been a little quiet without you. How are you doing?"

    try:
        msg = AgentMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=content,
            persona_id="maria",
            metadata={"absence_checkin": True, "days_absent": days_since},
        )

        # Push via WebSocket
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"support_group_{patient_id}",
                {
                    "type": "support_group_message",
                    "message_id": str(msg.id),
                    "persona_id": maria.id,
                    "persona_name": maria.name,
                    "content": content,
                    "avatar_color": maria.avatar_color,
                    "avatar_color_dark": maria.avatar_color_dark,
                    "avatar_initials": maria.avatar_initials,
                },
            )

        return {"success": True, "days_absent": days_since}

    except Exception as e:
        logger.error(f"Absence check-in failed for {patient_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=2**self.request.retries) from None
        return {"error": str(e)}
