"""Patient views."""

import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse
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

    if settings.DEBUG:
        from .models import Patient

        context["all_patients"] = Patient.objects.select_related("user").all()[:20]

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

    try:
        from apps.agents.services import process_patient_message

        result = process_patient_message(patient, message_text, channel="chat")

        # Render the message bubble HTML fragment
        html = render_to_string(
            "components/_message_bubble.html",
            {"message": result["agent_message"]},
            request=request,
        )

        response = HttpResponse(html)
        if result["escalate"]:
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


@require_POST
def patient_voice_send_view(request):
    """Handle voice message submission via HTMX.

    Accepts audio file upload, transcribes it, and processes through
    the same AI workflow as text chat.
    """
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)

    audio_file = request.FILES.get("audio")
    if not audio_file:
        return HttpResponse(status=400)

    # Validate file size
    max_size = getattr(settings, "VOICE_MEMO_MAX_SIZE_MB", 10) * 1024 * 1024
    if audio_file.size > max_size:
        return HttpResponse("File too large", status=413)

    # Validate content type
    if not audio_file.content_type.startswith("audio/"):
        return HttpResponse("Invalid file type", status=415)

    try:
        # Save audio file
        file_id = uuid.uuid4()
        voice_dir = Path(settings.MEDIA_ROOT) / "voice_memos" / str(patient.id)
        voice_dir.mkdir(parents=True, exist_ok=True)

        ext = audio_file.name.rsplit(".", 1)[-1] if "." in audio_file.name else "webm"
        file_path = voice_dir / f"{file_id}.{ext}"

        with open(file_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        # Transcribe
        from apps.messages_app.transcription import get_transcription_client

        client = get_transcription_client()
        audio_data = file_path.read_bytes()
        transcription = client.transcribe(audio_data, format=ext)

        if not transcription:
            transcription = "(Voice message — transcription unavailable)"

        # Process through AI workflow
        from django.urls import reverse

        from apps.agents.services import process_patient_message

        audio_url = reverse("patients:voice_file", kwargs={"file_id": file_id})
        result = process_patient_message(patient, transcription, channel="voice", audio_url=audio_url)

        # Render the message bubble HTML fragment
        html = render_to_string(
            "components/_message_bubble.html",
            {"message": result["agent_message"]},
            request=request,
        )

        response = HttpResponse(html)
        if result["escalate"]:
            response["HX-Trigger"] = "escalation"
        return response

    except Exception:
        logger.exception("Voice send failed for patient %s", patient.id)
        return HttpResponse(
            '<div class="flex justify-start" role="alert">'
            '<div class="max-w-[85%]">'
            '<div class="px-4 py-2.5 text-lg leading-relaxed"'
            ' style="background-color: #FEE2E2; color: #991B1B;'
            ' border-radius: 16px 16px 16px 4px;">'
            "Couldn't process audio. Please try again."
            "</div></div></div>",
            status=200,
        )


def patient_voice_file_view(request, file_id):
    """Serve voice audio file with authentication check."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)

    # Find the file in the patient's voice memo directory
    voice_dir = Path(settings.MEDIA_ROOT) / "voice_memos" / str(patient.id)

    # Look for any extension with this file_id
    matching = list(voice_dir.glob(f"{file_id}.*")) if voice_dir.exists() else []

    if not matching:
        return HttpResponse("Recording expired", status=404)

    file_path = matching[0]
    ext = file_path.suffix.lstrip(".")
    content_type = f"audio/{ext}" if ext != "webm" else "audio/webm"

    return FileResponse(file_path.open("rb"), content_type=content_type)


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

    elif action == "simulate_sms":
        _dev_simulate_sms(request)

    return redirect("patients:dashboard")


def _dev_simulate_sms(request):
    """Simulate an inbound SMS for dev toolbar."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return
    sms_text = request.POST.get("sms_text", "").strip()
    if not sms_text:
        return
    from apps.messages_app.services import SMSService

    phone = getattr(patient.user, "phone_number", "+15550000000")
    sms_service = SMSService()
    sms_service.handle_inbound_sms(
        from_number=str(phone),
        body=sms_text,
    )
