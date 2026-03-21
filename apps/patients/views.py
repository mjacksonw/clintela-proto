"""Patient views."""

import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages as django_messages
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
        from apps.agents.models import AgentConversation

        conversation = (
            AgentConversation.objects.filter(patient=patient, status="active", clinician__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if conversation:
            msg_objects = conversation.messages.prefetch_related(
                "citations__knowledge_doc__source",
            ).order_by("created_at")[:50]
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

        # When a clinician has control, no AI response is generated.
        # Return empty 200 — JS detects empty response and hides typing indicator.
        if result["agent_message"] is None:
            return HttpResponse("")

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

        allowed_audio_extensions = {"webm", "wav", "mp3", "ogg", "m4a", "mp4", "aac", "flac"}
        ext = audio_file.name.rsplit(".", 1)[-1].lower() if "." in audio_file.name else "webm"
        if ext not in allowed_audio_extensions:
            ext = "webm"
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


def patient_consent_view(request):
    """Consent management page — view current consent status."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return redirect("accounts:start")

    from .models import ConsentRecord

    consent_config = [
        {
            "type": "ai_interaction",
            "label": "AI-Powered Care Assistance",
            "description": (
                "Allow Clintela's AI agents to help answer your recovery questions using clinical knowledge."
            ),
            "icon": "bot",
            "color": "var(--color-primary)",
        },
        {
            "type": "data_sharing_caregiver",
            "label": "Share with Caregivers",
            "description": (
                "Allow your invited family members or caregivers to view your recovery status and chat history."
            ),
            "icon": "users",
            "color": "#0D9488",
        },
        {
            "type": "communication_sms",
            "label": "SMS Messages",
            "description": "Receive recovery check-ins and care reminders via text message.",
            "icon": "message-square",
            "color": "#D97706",
        },
        {
            "type": "communication_email",
            "label": "Email Updates",
            "description": "Receive recovery summaries and appointment reminders by email.",
            "icon": "mail",
            "color": "#7C3AED",
        },
        {
            "type": "data_sharing_research",
            "label": "Anonymized Research",
            "description": "Allow your de-identified data to be used for improving post-surgical care outcomes.",
            "icon": "flask-conical",
            "color": "#059669",
        },
    ]

    consent_items = []
    for cfg in consent_config:
        latest = ConsentRecord.objects.filter(patient=patient, consent_type=cfg["type"]).order_by("-granted_at").first()
        consent_items.append(
            {
                **cfg,
                "granted": latest.granted if latest else False,
                "last_changed": latest.granted_at if latest else None,
            }
        )

    return render(
        request,
        "patients/consent.html",
        {
            "patient": patient,
            "consent_items": consent_items,
        },
    )


@require_POST
def patient_consent_toggle_view(request):
    """Toggle a consent setting via POST."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)

    from .models import ConsentRecord

    consent_type = request.POST.get("consent_type", "")
    granted = request.POST.get("granted", "true") == "true"

    valid_types = [c[0] for c in ConsentRecord.CONSENT_TYPE_CHOICES]
    if consent_type not in valid_types:
        return HttpResponse(status=400)

    ConsentRecord.objects.create(
        patient=patient,
        consent_type=consent_type,
        granted=granted,
        granted_by=patient.user,
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    action = "enabled" if granted else "disabled"
    label = dict(ConsentRecord.CONSENT_TYPE_CHOICES).get(consent_type, consent_type)
    django_messages.success(request, f"{label} {action}.")

    return redirect("patients:consent")


def patient_caregivers_view(request):
    """Caregiver management — view active caregivers and send invitations."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return redirect("accounts:start")

    from apps.caregivers.models import CaregiverInvitation, CaregiverRelationship

    relationships = CaregiverRelationship.objects.filter(
        patient=patient,
        is_active=True,
    ).select_related("caregiver__user")

    invitations = CaregiverInvitation.objects.filter(
        patient=patient,
        status="pending",
    ).order_by("-created_at")

    return render(
        request,
        "patients/caregivers.html",
        {
            "patient": patient,
            "relationships": relationships,
            "invitations": invitations,
            "relationship_choices": CaregiverInvitation.RELATIONSHIP_CHOICES,
        },
    )


@require_POST
def patient_caregiver_invite_view(request):
    """Send a caregiver invitation."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)

    from apps.caregivers.models import CaregiverInvitation

    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()
    relationship = request.POST.get("relationship", "").strip()

    if not name or not relationship:
        django_messages.error(request, "Name and relationship are required.")
        return redirect("patients:caregivers")

    if not email and not phone:
        django_messages.error(request, "Please provide an email or phone number.")
        return redirect("patients:caregivers")

    valid_rels = [c[0] for c in CaregiverInvitation.RELATIONSHIP_CHOICES]
    if relationship not in valid_rels:
        django_messages.error(request, "Invalid relationship type.")
        return redirect("patients:caregivers")

    invitation = CaregiverInvitation.objects.create(
        patient=patient,
        name=name,
        email=email,
        phone=phone,
        relationship=relationship,
    )

    django_messages.success(request, f"Invitation sent to {name}.")
    logger.info("Caregiver invitation created: %s for patient %s", invitation.id, patient.id)

    return redirect("patients:caregivers")


@require_POST
def patient_caregiver_revoke_view(request):
    """Revoke a caregiver invitation or relationship."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)

    from apps.caregivers.models import CaregiverInvitation, CaregiverRelationship, InvalidInvitationError

    invitation_id = request.POST.get("invitation_id")
    relationship_id = request.POST.get("relationship_id")

    if invitation_id:
        try:
            invitation = CaregiverInvitation.objects.get(pk=invitation_id, patient=patient)
            invitation.revoke()
            django_messages.success(request, f"Invitation to {invitation.name} revoked.")
        except CaregiverInvitation.DoesNotExist:
            django_messages.error(request, "Invitation not found.")
        except InvalidInvitationError as e:
            django_messages.error(request, str(e))

    elif relationship_id:
        try:
            rel = CaregiverRelationship.objects.get(pk=relationship_id, patient=patient)
            rel.is_active = False
            rel.save(update_fields=["is_active"])
            name = rel.caregiver.user.get_full_name()
            django_messages.success(request, f"Access for {name} has been removed.")
        except CaregiverRelationship.DoesNotExist:
            django_messages.error(request, "Caregiver not found.")

    return redirect("patients:caregivers")


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
