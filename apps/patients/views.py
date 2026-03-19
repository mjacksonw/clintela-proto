"""Patient views."""

import logging
import time

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _get_authenticated_patient(request):
    """Return the authenticated Patient or None."""
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
    """Generate contextual suggestion chips based on patient pathway."""
    from apps.pathways.models import PatientPathway

    try:
        pathway = PatientPathway.objects.filter(patient=patient, is_active=True).first()
        if pathway and hasattr(pathway, "milestones"):
            milestones = pathway.milestones.filter(is_completed=False).order_by("expected_day")[:3]
            if milestones:
                chips = []
                for m in milestones:
                    if hasattr(m, "expected_symptoms") and m.expected_symptoms:
                        chips.append(f"Is {m.expected_symptoms.split(',')[0].strip().lower()} normal?")
                    elif m.title:
                        chips.append(f"Tell me about {m.title.lower()}")
                if chips:
                    return chips[:3]
    except Exception:
        logger.debug("No pathway data for suggestion chips")

    return ["Is this normal?", "My medications", "Talk to my care team"]


def patient_dashboard_view(request):
    """Patient dashboard with chat sidebar."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return redirect("accounts:start")

    # Load conversation history for chat sidebar
    messages = []
    try:
        from apps.agents.services import ConversationService

        conversation = ConversationService.get_or_create_conversation(patient)
        msg_objects = conversation.messages.order_by("created_at")[:50]
        messages = list(msg_objects)
    except Exception:
        logger.exception("Failed to load conversation history")

    # Build context
    days_post_op = patient.days_post_op()
    suggestion_chips = _get_suggestion_chips(patient)

    context = {
        "patient": patient,
        "messages": messages,
        "days_post_op": days_post_op,
        "suggestion_chips": suggestion_chips,
        "debug": settings.DEBUG,
    }

    return render(request, "patients/dashboard.html", context)


@require_POST
def patient_chat_send_view(request):
    """Handle chat message submission via HTMX."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)

    message_text = request.POST.get("message", "").strip()
    if not message_text:
        return HttpResponse(status=400)

    start_time = time.time()

    try:
        from apps.agents.services import ConversationService, EscalationService
        from apps.agents.workflow import get_workflow

        # Get or create conversation
        conversation = ConversationService.get_or_create_conversation(patient)

        # Save user message
        ConversationService.add_message(
            conversation=conversation,
            role="user",
            content=message_text,
        )

        # Build context for workflow
        context = {
            "patient": {
                "name": patient.user.get_full_name(),
                "surgery_type": patient.surgery_type or "General Surgery",
                "days_post_op": patient.days_post_op() or 0,
                "hospital": patient.hospital.name if patient.hospital else "Unknown",
            },
        }

        # Call async workflow from sync view
        workflow = get_workflow()
        result = async_to_sync(workflow.process_message)(message_text, context)

        response_text = result.get("response", "").strip()
        if not response_text:
            response_text = "I'm sorry, I wasn't able to process that. Could you try rephrasing?"

        agent_type = result.get("agent_type", "care_coordinator")
        escalate = result.get("escalate", False)
        confidence = result.get("metadata", {}).get("confidence_score")

        # Save agent message
        agent_message = ConversationService.add_message(
            conversation=conversation,
            role="assistant",
            content=response_text,
            agent_type=agent_type,
            confidence_score=confidence,
            escalation_triggered=escalate,
            escalation_reason=result.get("escalation_reason", ""),
        )

        # Handle escalation
        if escalate:
            EscalationService.create_escalation(
                patient=patient,
                conversation=conversation,
                severity="high",
                reason=result.get("escalation_reason", "Agent-triggered escalation"),
            )

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Chat response: patient=%s agent=%s elapsed=%dms escalation=%s",
            patient.id,
            agent_type,
            elapsed_ms,
            escalate,
        )

        # Render the message bubble HTML fragment
        html = render_to_string(
            "components/_message_bubble.html",
            {"message": agent_message},
            request=request,
        )

        response = HttpResponse(html)
        if escalate:
            response["HX-Trigger"] = "escalation"
        return response

    except Exception:
        logger.exception("Chat send failed for patient %s", patient.id)
        return HttpResponse(
            '<div class="flex justify-start" role="alert">'
            '<div class="max-w-[85%]">'
            '<div class="px-4 py-2.5 text-lg leading-relaxed"'
            ' style="background-color: #FEE2E2; color: #991B1B;'
            ' border-radius: 16px 16px 16px 4px;">'
            "Something went wrong. Please try again."
            "</div></div></div>",
            status=200,
        )


def patient_dev_actions_view(request):
    """Dev toolbar actions — DEBUG only."""
    if not settings.DEBUG:
        from django.http import Http404

        raise Http404

    if request.method != "POST":
        return HttpResponse(status=405)

    action = request.POST.get("action")

    if action == "clear_conversation":
        patient = _get_authenticated_patient(request)
        if patient:
            from apps.agents.models import AgentConversation

            AgentConversation.objects.filter(patient=patient).delete()

    elif action == "switch_patient":
        from .models import Patient

        patient_id = request.POST.get("patient_id")
        if patient_id:
            try:
                patient = Patient.objects.get(id=patient_id)
                request.session["patient_id"] = str(patient.id)
                request.session["authenticated"] = True
            except Patient.DoesNotExist:
                pass

    return redirect("patients:dashboard")
