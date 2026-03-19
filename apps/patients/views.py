"""Patient views."""

import logging
import time

from asgiref.sync import async_to_sync
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from apps.agents.services import ContextService, ConversationService, EscalationService
from apps.agents.workflow import get_workflow

logger = logging.getLogger(__name__)


def _get_authenticated_patient(request):
    """Get authenticated patient from session, or None."""
    patient_id = request.session.get("patient_id")
    authenticated = request.session.get("authenticated")

    if not patient_id or not authenticated:
        return None

    from .models import Patient

    try:
        return Patient.objects.select_related("user", "hospital").get(id=patient_id)
    except Patient.DoesNotExist:
        return None


def _get_suggestion_chips(patient):
    """Get contextual suggestion chips from pathway data."""
    from apps.pathways.models import PathwayMilestone

    try:
        active_pathway = patient.pathways.filter(status="active").select_related("pathway").first()

        if not active_pathway:
            return []

        days_post_op = patient.days_post_op()
        if days_post_op is None:
            return []

        milestone = (
            PathwayMilestone.objects.filter(
                pathway=active_pathway.pathway,
                day__lte=days_post_op,
                is_active=True,
            )
            .order_by("-day")
            .first()
        )

        if not milestone:
            return []

        chips = []
        if milestone.expected_symptoms:
            symptoms = milestone.expected_symptoms
            if isinstance(symptoms, list) and symptoms:
                chips.append(f"Is {symptoms[0].lower()} normal?")
        if milestone.activities:
            activities = milestone.activities
            if isinstance(activities, list) and activities:
                chips.append(f"Can I {activities[0].lower()}?")
        chips.append("My pain today")
        return chips[:3]
    except Exception:
        return []


def patient_dashboard_view(request):
    """Patient dashboard with chat sidebar and recovery info."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return redirect("accounts:start")

    # Get conversation history for chat sidebar
    conversation = ConversationService.get_or_create_conversation(patient)
    messages = conversation.messages.order_by("created_at")[:50]

    # Get pathway context for dashboard cards
    pathway_context = ContextService.get_pathway_context(patient)

    # Get suggestion chips
    suggestion_chips = _get_suggestion_chips(patient)

    return render(
        request,
        "patients/dashboard.html",
        {
            "patient": patient,
            "messages": messages,
            "pathway_context": pathway_context,
            "suggestion_chips": suggestion_chips,
            "debug": request.META.get("SERVER_NAME") == "localhost",
        },
    )


@require_POST
def patient_chat_send_view(request):
    """HTMX endpoint: process a chat message and return HTML fragment."""
    # Auth check
    patient_id = request.session.get("patient_id")
    authenticated = request.session.get("authenticated")
    if not patient_id or not authenticated:
        return HttpResponse(status=403)

    message_text = request.POST.get("message", "").strip()
    if not message_text:
        return HttpResponseBadRequest("Message cannot be empty")

    start_time = time.time()

    # Get patient
    from .models import Patient

    try:
        patient = Patient.objects.select_related("user", "hospital").get(id=patient_id)
    except Patient.DoesNotExist:
        return HttpResponse(status=403)

    # Get or create conversation
    conversation = ConversationService.get_or_create_conversation(patient)

    # Save user message
    ConversationService.add_message(conversation, "user", message_text)

    # Assemble context
    context = ContextService.assemble_full_context(patient, conversation)

    # Process through workflow (async → sync bridge)
    workflow = get_workflow()
    try:
        result = async_to_sync(workflow.process_message)(message_text, context)
    except Exception as e:
        logger.error(f"Workflow error: {e}")
        result = {
            "response": "I'm sorry, I wasn't able to process that. Could you try rephrasing?",
            "agent_type": "care_coordinator",
            "escalate": False,
            "escalation_reason": "",
            "metadata": {},
        }

    # Guard empty response
    response_text = result.get("response", "").strip()
    if not response_text:
        response_text = "I'm sorry, I wasn't able to process that. Could you try rephrasing?"

    # Save agent response
    agent_msg = ConversationService.add_message(
        conversation,
        "assistant",
        response_text,
        agent_type=result.get("agent_type", "care_coordinator"),
        confidence_score=result.get("metadata", {}).get("confidence"),
        escalation_triggered=result.get("escalate", False),
        escalation_reason=result.get("escalation_reason", ""),
        metadata=result.get("metadata", {}),
    )

    # Handle escalation
    if result.get("escalate"):
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

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Chat message processed: agent=%s time=%dms escalation=%s",
        result.get("agent_type"),
        elapsed_ms,
        result.get("escalate", False),
    )

    # Render the message bubble HTML fragment
    html = render_to_string(
        "components/_message_bubble.html",
        {"message": agent_msg},
        request=request,
    )

    response = HttpResponse(html)
    if result.get("escalate"):
        response["HX-Trigger"] = "escalation"

    return response


@require_POST
def patient_dev_actions_view(request):
    """Dev toolbar actions — DEBUG only."""
    from django.conf import settings

    if not settings.DEBUG:
        from django.http import Http404

        raise Http404

    patient = _get_authenticated_patient(request)
    if not patient:
        return redirect("accounts:start")

    action = request.POST.get("action")

    if action == "clear_conversation":
        from apps.agents.models import AgentConversation

        AgentConversation.objects.filter(patient=patient).delete()

    return redirect("patients:dashboard")
