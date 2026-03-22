"""Views for clinician dashboard."""

import logging

from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.agents.models import AgentConversation, AgentMessage, Escalation
from apps.agents.services import EscalationService
from apps.clinicians.auth import clinician_required
from apps.clinicians.models import ClinicianNote
from apps.clinicians.services import (
    ClinicianResearchService,
    HandoffService,
    PatientListService,
    SchedulingService,
    TakeControlService,
    TimelineService,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def clinician_login_view(request):
    """Login view for clinicians."""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None and user.role == "clinician":
            login(request, user)
            logger.info("Clinician login: user=%s", user.id)
            return redirect("clinicians:dashboard")

        return render(
            request,
            "clinicians/login.html",
            {
                "error": "Invalid credentials or not a clinician account.",
            },
        )

    return render(request, "clinicians/login.html")


def clinician_logout_view(request):
    """Logout and redirect to login."""
    logger.info("Clinician logout: user=%s", request.user.id if request.user.is_authenticated else "anon")
    logout(request)
    return redirect("clinicians:login")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@clinician_required
def dashboard_view(request):
    """Main three-panel dashboard."""
    clinician = request.clinician

    # Handoff summary
    last_login = request.user.last_login
    is_first_login = last_login is None
    handoff = None if is_first_login else HandoffService.get_handoff_summary(clinician, last_login)

    # Update last_login
    request.user.last_login = timezone.now()
    request.user.save(update_fields=["last_login"])

    # Next appointment for footer toast
    next_appointment = SchedulingService.get_next_appointment(clinician)

    # Hospital ID for dashboard WebSocket connection
    hospital_id = clinician.hospitals.values_list("id", flat=True).first()

    # Pending escalation count for notification bell
    hospital_ids = clinician.hospitals.values_list("id", flat=True)
    pending_escalation_count = Escalation.objects.filter(
        status="pending",
        patient__hospital_id__in=hospital_ids,
    ).count()

    return render(
        request,
        "clinicians/dashboard.html",
        {
            "clinician": clinician,
            "handoff": handoff,
            "is_first_login": is_first_login,
            "next_appointment": next_appointment,
            "hospital_id": hospital_id,
            "pending_escalation_count": pending_escalation_count,
        },
    )


# ---------------------------------------------------------------------------
# Patient List (Left Panel — HTMX fragment)
# ---------------------------------------------------------------------------


@clinician_required
@require_GET
def patient_list_fragment(request):
    """HTMX fragment: patient list with search and sort."""
    sort = request.GET.get("sort", "severity")
    search = request.GET.get("search", "").strip()

    patients = PatientListService.get_patients_for_clinician(
        request.clinician,
        sort=sort,
        search=search,
    )

    # Build status lines
    patient_data = []
    for p in patients:
        patient_data.append(
            {
                "patient": p,
                "status_line": PatientListService.get_status_line(p),
                "days_post_op": p.days_post_op(),
            }
        )

    html = render_to_string(
        "clinicians/components/_patient_list.html",
        {"patient_data": patient_data, "sort": sort, "search": search},
        request=request,
    )
    return HttpResponse(html)


# ---------------------------------------------------------------------------
# Patient Detail Tabs (Center Panel — HTMX fragments)
# ---------------------------------------------------------------------------


@clinician_required
@require_GET
def patient_detail_fragment(request, patient_id):
    """HTMX fragment: Details tab."""
    patient = request.patient

    # Timeline (collapsed by day)
    timeline = TimelineService.get_timeline(patient)

    # Pending escalations
    escalations = Escalation.objects.filter(
        patient=patient,
        status__in=["pending", "acknowledged"],
    ).order_by("-created_at")

    # Notes
    notes = ClinicianNote.objects.filter(patient=patient).order_by("-created_at")[:20]

    # Upcoming appointments
    appointments = SchedulingService.get_patient_appointments(patient)

    html = render_to_string(
        "clinicians/components/_tab_details.html",
        {
            "patient": patient,
            "timeline": timeline,
            "escalations": escalations,
            "notes": notes,
            "appointments": appointments,
        },
        request=request,
    )
    return HttpResponse(html)


@clinician_required
@require_GET
def patient_care_plan_fragment(request, patient_id):
    """HTMX fragment: Care Plan tab."""
    patient = request.patient

    # Get active pathway + milestones
    from apps.pathways.models import PatientMilestoneCheckin, PatientPathway

    active_pathway = (
        PatientPathway.objects.filter(
            patient=patient,
            status="active",
        )
        .select_related("pathway")
        .first()
    )

    milestones = []
    if active_pathway:
        from apps.pathways.models import PathwayMilestone

        milestones = PathwayMilestone.objects.filter(
            pathway=active_pathway.pathway,
        ).order_by("day")

        # Annotate with checkin status
        checkin_map = {
            c.milestone_id: c
            for c in PatientMilestoneCheckin.objects.filter(
                patient=patient,
                milestone__in=milestones,
            )
        }
        milestones = [{"milestone": m, "checkin": checkin_map.get(m.id)} for m in milestones]

    html = render_to_string(
        "clinicians/components/_tab_care_plan.html",
        {
            "patient": patient,
            "active_pathway": active_pathway,
            "milestones": milestones,
        },
        request=request,
    )
    return HttpResponse(html)


@clinician_required
@require_GET
def patient_research_fragment(request, patient_id):
    """HTMX fragment: Research tab (clinician LLM chat)."""
    patient = request.patient
    clinician = request.clinician

    conversation = ClinicianResearchService.get_or_create_research_conversation(
        patient,
        clinician,
    )
    messages = AgentMessage.objects.filter(
        conversation=conversation,
    ).order_by("created_at")[:50]

    html = render_to_string(
        "clinicians/components/_tab_research.html",
        {
            "patient": patient,
            "conversation": conversation,
            "messages": messages,
        },
        request=request,
    )
    return HttpResponse(html)


@clinician_required
@require_POST
def research_chat_send_view(request, patient_id):
    """POST: Send a research query and return the response fragment."""
    patient = request.patient
    clinician = request.clinician
    message = request.POST.get("message", "").strip()
    specialist_override = request.POST.get("specialist_override", "").strip()

    if not message:
        return HttpResponseBadRequest("Message is required.")

    result = ClinicianResearchService.send_research_message(
        patient,
        clinician,
        message,
        specialist_override=specialist_override,
    )

    html = render_to_string(
        "clinicians/components/_research_message.html",
        {
            "message": result["message"],
            "response": result["response"],
            "agent_type": result["agent_type"],
            "query": message,
        },
        request=request,
    )
    return HttpResponse(html)


def _render_tools_html(request, patient):
    """Render tools tab HTML fragment (shared by GET and lifecycle POST)."""
    from apps.caregivers.models import CaregiverRelationship
    from apps.pathways.models import ClinicalPathway, PatientPathway
    from apps.patients.models import ConsentRecord, Patient

    consents = ConsentRecord.objects.filter(patient=patient).order_by("-granted_at")
    caregivers = CaregiverRelationship.objects.filter(
        patient=patient,
    ).select_related("caregiver__user")
    valid_transitions = Patient.LIFECYCLE_TRANSITIONS.get(
        patient.lifecycle_status,
        [],
    )

    # Pathway assignment context
    active_pathway = PatientPathway.objects.filter(patient=patient, status="active").select_related("pathway").first()
    available_pathways = ClinicalPathway.objects.filter(is_active=True).order_by("name")

    return render_to_string(
        "clinicians/components/_tab_tools.html",
        {
            "patient": patient,
            "consents": consents,
            "caregivers": caregivers,
            "valid_transitions": valid_transitions,
            "active_pathway": active_pathway,
            "available_pathways": available_pathways,
        },
        request=request,
    )


@clinician_required
@require_GET
def patient_tools_fragment(request, patient_id):
    """HTMX fragment: Tools tab."""
    return HttpResponse(_render_tools_html(request, request.patient))


# ---------------------------------------------------------------------------
# Patient Chat (Right Panel — HTMX fragment)
# ---------------------------------------------------------------------------


def _render_chat_html(request, patient):
    """Render patient chat HTML fragment (shared by GET and release views)."""
    conversation = (
        AgentConversation.objects.filter(
            patient=patient,
            clinician__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )

    messages = []
    paused_by = None
    if conversation:
        messages = AgentMessage.objects.filter(
            conversation=conversation,
        ).order_by("created_at")[:100]
        conversation.refresh_from_db()
        paused_by = conversation.paused_by

    current_user = request.user
    is_controlled_by_me = paused_by == current_user if paused_by else False
    is_controlled_by_other = paused_by is not None and not is_controlled_by_me

    return render_to_string(
        "clinicians/components/_patient_chat.html",
        {
            "patient": patient,
            "conversation": conversation,
            "messages": messages,
            "paused_by": paused_by,
            "is_controlled_by_me": is_controlled_by_me,
            "is_controlled_by_other": is_controlled_by_other,
        },
        request=request,
    )


@clinician_required
@require_GET
def patient_chat_fragment(request, patient_id):
    """HTMX fragment: patient's AI conversation thread."""
    return HttpResponse(_render_chat_html(request, request.patient))


# ---------------------------------------------------------------------------
# Message Injection + Take Control
# ---------------------------------------------------------------------------


@clinician_required
@require_POST
def inject_chat_message_view(request, patient_id):
    """POST: Clinician sends a message into the patient's conversation."""
    patient = request.patient
    content = request.POST.get("message", "").strip()

    if not content:
        return HttpResponseBadRequest("Message is required.")

    # Get or create the patient's conversation
    conversation = (
        AgentConversation.objects.filter(
            patient=patient,
            clinician__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )

    if not conversation:
        conversation = AgentConversation.objects.create(
            patient=patient,
            agent_type="supervisor",
            status="active",
        )

    # Implicitly take control if not already
    if not conversation.paused_by:
        taken = TakeControlService.take_control(conversation, request.user)
        if not taken:
            return HttpResponse(
                render_to_string(
                    "clinicians/components/_take_control_error.html",
                    {"error": "Another clinician may have taken control."},
                    request=request,
                )
            )
    elif conversation.paused_by != request.user:
        return HttpResponse(
            render_to_string(
                "clinicians/components/_take_control_error.html",
                {"error": f"{conversation.paused_by.get_full_name()} is currently responding."},
                request=request,
            )
        )

    # Create the clinician message
    try:
        msg = AgentMessage.objects.create(
            conversation=conversation,
            role="assistant",
            agent_type="clinician",
            content=content,
            metadata={
                "clinician_user_id": str(request.user.id),
                "clinician_name": request.user.get_full_name(),
            },
        )
    except Exception:
        logger.exception("Failed to inject clinician message")
        return HttpResponseBadRequest("Failed to send message. Please try again.")

    # Push to patient's notification WebSocket group
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"patient_{patient.id}_notifications",
            {
                "type": "chat.message",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "agent_type": "clinician",
                    "clinician_name": request.user.get_full_name(),
                    "created_at": msg.created_at.isoformat(),
                },
            },
        )
    except Exception:
        logger.warning("Channel layer unavailable for patient push, patient=%s", patient.id)

    # Update paused_at to reset inactivity timer
    AgentConversation.objects.filter(pk=conversation.pk).update(paused_at=timezone.now())

    # Return the full chat panel so take-control bar reflects new state
    return HttpResponse(_render_chat_html(request, patient))


@clinician_required
@require_POST
def release_take_control_view(request, patient_id):
    """POST: Release clinician control of a patient's conversation."""
    patient = request.patient

    conversation = (
        AgentConversation.objects.filter(
            patient=patient,
            clinician__isnull=True,
            paused_by=request.user,
        )
        .order_by("-created_at")
        .first()
    )

    if conversation:
        TakeControlService.release_control(conversation, request.user)

    # Return updated chat panel
    return HttpResponse(_render_chat_html(request, patient))


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


@clinician_required
@require_POST
def add_note_view(request, patient_id):
    """POST: Add a clinician note for a patient."""
    patient = request.patient
    content = request.POST.get("content", "").strip()
    note_type = request.POST.get("note_type", "quick_note")
    valid_note_types = {c[0] for c in ClinicianNote.NOTE_TYPE_CHOICES}

    if not content:
        return HttpResponseBadRequest("Note content is required.")
    if note_type not in valid_note_types:
        return HttpResponseBadRequest("Invalid note type.")

    note = ClinicianNote.objects.create(
        patient=patient,
        clinician=request.clinician,
        content=content,
        note_type=note_type,
    )

    html = render_to_string(
        "clinicians/components/_note_item.html",
        {"note": note},
        request=request,
    )
    return HttpResponse(html)


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------


@clinician_required
@require_POST
def acknowledge_escalation_view(request, escalation_id):
    """POST: Acknowledge an escalation."""
    try:
        escalation = Escalation.objects.get(id=escalation_id)
    except Escalation.DoesNotExist:
        return HttpResponseBadRequest("Escalation not found.")

    # Verify hospital access
    clinician_hospital_ids = set(request.clinician.hospitals.values_list("id", flat=True))
    if escalation.patient.hospital_id not in clinician_hospital_ids:
        return HttpResponse(status=403)

    EscalationService.acknowledge_escalation(str(escalation.id), request.user.id)
    escalation.refresh_from_db()

    html = render_to_string(
        "clinicians/components/_escalation_badge.html",
        {"escalation": escalation},
        request=request,
    )
    return HttpResponse(html)


@clinician_required
@require_POST
def resolve_escalation_view(request, escalation_id):
    """POST: Resolve an escalation."""
    try:
        escalation = Escalation.objects.get(id=escalation_id)
    except Escalation.DoesNotExist:
        return HttpResponseBadRequest("Escalation not found.")

    clinician_hospital_ids = set(request.clinician.hospitals.values_list("id", flat=True))
    if escalation.patient.hospital_id not in clinician_hospital_ids:
        return HttpResponse(status=403)

    EscalationService.resolve_escalation(str(escalation.id))
    escalation.refresh_from_db()

    html = render_to_string(
        "clinicians/components/_escalation_badge.html",
        {"escalation": escalation},
        request=request,
    )
    return HttpResponse(html)


@clinician_required
@require_POST
def bulk_acknowledge_escalations_view(request):
    """POST: Bulk acknowledge multiple escalations."""
    escalation_ids = request.POST.getlist("escalation_ids")
    if not escalation_ids:
        return HttpResponseBadRequest("No escalations selected.")

    clinician_hospital_ids = set(request.clinician.hospitals.values_list("id", flat=True))

    acknowledged = 0
    failed = 0
    for eid in escalation_ids:
        try:
            esc = Escalation.objects.get(id=eid, status="pending")
            if esc.patient.hospital_id in clinician_hospital_ids:
                EscalationService.acknowledge_escalation(str(esc.id), request.user.id)
                acknowledged += 1
            else:
                failed += 1
        except Escalation.DoesNotExist:
            failed += 1

    return JsonResponse(
        {
            "acknowledged": acknowledged,
            "failed": failed,
            "total": len(escalation_ids),
        }
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@clinician_required
@require_POST
def lifecycle_transition_view(request, patient_id):
    """POST: Transition a patient's lifecycle status."""
    patient = request.patient
    new_status = request.POST.get("new_status", "").strip()
    reason = request.POST.get("reason", "Clinician dashboard transition")

    if not new_status:
        return HttpResponseBadRequest("New status is required.")

    from apps.patients.models import InvalidLifecycleTransitionError

    try:
        patient.transition_lifecycle(new_status, reason=reason)
    except (ValueError, InvalidLifecycleTransitionError) as e:
        return HttpResponseBadRequest(str(e))

    # Return updated tools tab
    return HttpResponse(_render_tools_html(request, patient))


# ---------------------------------------------------------------------------
# Pathway Assignment
# ---------------------------------------------------------------------------


@clinician_required
@require_POST
def assign_pathway_view(request, patient_id):
    """POST: Assign or change a care pathway for a patient."""
    from apps.pathways.models import ClinicalPathway, PatientPathway

    patient = request.patient
    pathway_id = request.POST.get("pathway_id", "").strip()

    if not pathway_id:
        return HttpResponseBadRequest("Pathway selection is required.")

    try:
        pathway = ClinicalPathway.objects.get(id=pathway_id, is_active=True)
    except ClinicalPathway.DoesNotExist:
        return HttpResponseBadRequest("Invalid pathway selected.")

    # Discontinue any existing active pathway
    PatientPathway.objects.filter(patient=patient, status="active").update(
        status="discontinued",
        completed_at=timezone.now(),
    )

    # Create new assignment
    PatientPathway.objects.create(
        patient=patient,
        pathway=pathway,
        status="active",
    )

    logger.info(
        "Clinician %s assigned pathway '%s' to patient %s",
        request.user.username,
        pathway.name,
        patient.id,
    )

    # Return updated tools tab
    return HttpResponse(_render_tools_html(request, patient))


@clinician_required
@require_POST
def unassign_pathway_view(request, patient_id):
    """POST: Discontinue the active care pathway for a patient."""
    from apps.pathways.models import PatientPathway

    patient = request.patient

    updated = PatientPathway.objects.filter(patient=patient, status="active").update(
        status="discontinued",
        completed_at=timezone.now(),
    )

    if not updated:
        return HttpResponseBadRequest("No active pathway to discontinue.")

    logger.info(
        "Clinician %s discontinued pathway for patient %s",
        request.user.username,
        patient.id,
    )

    return HttpResponse(_render_tools_html(request, patient))


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


@clinician_required
def schedule_view(request):
    """Full-page scheduling view."""
    clinician = request.clinician

    from datetime import date, timedelta

    # Default to current week
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_offset = int(request.GET.get("week_offset", 0))
    week_start += timedelta(weeks=week_offset)

    schedule = SchedulingService.get_weekly_schedule(clinician, week_start)

    # Build day grid (Mon-Fri for clinical)
    days = []
    for i in range(5):
        d = week_start + timedelta(days=i)
        day_appointments = [a for a in schedule["appointments"] if a.scheduled_start.date() == d]
        day_availability = [a for a in schedule["availability"] if a.day_of_week == i]
        days.append(
            {
                "date": d,
                "appointments": day_appointments,
                "availability": day_availability,
            }
        )

    # All patients for appointment creation form
    from apps.patients.models import Patient

    hospital_ids = clinician.hospitals.values_list("id", flat=True)
    patients = (
        Patient.objects.filter(
            hospital_id__in=hospital_ids,
            is_active=True,
        )
        .select_related("user")
        .order_by("user__last_name")
    )

    return render(
        request,
        "clinicians/schedule.html",
        {
            "clinician": clinician,
            "days": days,
            "week_start": week_start,
            "week_end": week_start + timedelta(days=4),
            "week_offset": week_offset,
            "patients": patients,
        },
    )


@clinician_required
@require_POST
def save_availability_view(request):
    """POST: Save clinician availability."""
    from apps.clinicians.models import ClinicianAvailability

    clinician = request.clinician
    try:
        day_of_week = int(request.POST.get("day_of_week", 0))
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Invalid day of week.")
    start_time = request.POST.get("start_time")
    end_time = request.POST.get("end_time")

    if not start_time or not end_time:
        return HttpResponseBadRequest("Start and end time are required.")

    ClinicianAvailability.objects.update_or_create(
        clinician=clinician,
        day_of_week=day_of_week,
        start_time=start_time,
        is_recurring=True,
        defaults={"end_time": end_time},
    )

    return redirect("clinicians:schedule")


@clinician_required
@require_POST
def create_appointment_view(request):
    """POST: Create an appointment."""
    from datetime import datetime

    from apps.clinicians.models import Appointment

    clinician = request.clinician
    patient_id = request.POST.get("patient_id")
    appointment_type = request.POST.get("appointment_type", "follow_up")
    start_str = request.POST.get("scheduled_start")
    end_str = request.POST.get("scheduled_end")
    notes = request.POST.get("notes", "")

    if not patient_id or not start_str or not end_str:
        return HttpResponseBadRequest("Patient, start, and end times are required.")

    valid_types = {c[0] for c in Appointment.TYPE_CHOICES}
    if appointment_type not in valid_types:
        return HttpResponseBadRequest("Invalid appointment type.")

    from apps.patients.models import Patient

    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return HttpResponseBadRequest("Patient not found.")

    # Verify hospital access
    clinician_hospital_ids = set(clinician.hospitals.values_list("id", flat=True))
    if patient.hospital_id not in clinician_hospital_ids:
        return HttpResponse(status=403)

    try:
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)
    except ValueError:
        return HttpResponseBadRequest("Invalid date format.")

    appointment = SchedulingService.create_appointment(
        clinician=clinician,
        patient=patient,
        start=start,
        end=end,
        appointment_type=appointment_type,
        created_by=request.user,
        notes=notes,
    )

    if appointment is None:
        return HttpResponseBadRequest("Time slot conflicts with an existing appointment.")

    return redirect("clinicians:schedule")


@clinician_required
@require_POST
def cancel_appointment_view(request, appointment_id):
    """POST: Cancel an appointment."""
    from apps.clinicians.models import Appointment

    try:
        appointment = Appointment.objects.get(
            id=appointment_id,
            clinician=request.clinician,
        )
    except Appointment.DoesNotExist:
        return HttpResponseBadRequest("Appointment not found.")

    appointment.status = "cancelled"
    appointment.save(update_fields=["status"])

    return redirect("clinicians:schedule")


# ---------------------------------------------------------------------------
# Export Handoff
# ---------------------------------------------------------------------------


@clinician_required
@require_GET
def export_handoff_view(request, patient_id):
    """GET: Generate structured handoff data for clipboard copy."""
    patient = request.patient

    # Build handoff summary from patient data
    escalations = Escalation.objects.filter(patient=patient).order_by("-created_at")[:10]
    notes = ClinicianNote.objects.filter(patient=patient).order_by("-created_at")[:10]

    handoff = {
        "patient": {
            "name": patient.user.get_full_name(),
            "mrn": patient.mrn,
            "status": patient.status,
            "lifecycle": patient.lifecycle_status,
            "surgery_type": patient.surgery_type,
            "days_post_op": patient.days_post_op(),
        },
        "escalations": [
            {
                "severity": e.severity,
                "reason": e.reason,
                "status": e.status,
                "created_at": str(e.created_at),
            }
            for e in escalations
        ],
        "recent_notes": [
            {
                "content": n.content,
                "note_type": n.note_type,
                "clinician": n.clinician.user.get_full_name(),
                "created_at": str(n.created_at),
            }
            for n in notes
        ],
        "generated_at": str(timezone.now()),
    }
    return JsonResponse(handoff)


# ---------------------------------------------------------------------------
# Timeline Day Expand (HTMX fragment)
# ---------------------------------------------------------------------------


@clinician_required
@require_GET
def timeline_day_fragment(request, patient_id, date):
    """HTMX fragment: expanded timeline events for a specific day."""
    patient = request.patient

    timeline = TimelineService.get_timeline(patient, days=90)

    from datetime import date as date_type

    parts = date.split("-")
    try:
        target_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return HttpResponseBadRequest("Invalid date.")

    day_events = []
    for group in timeline:
        if group["date"] == target_date:
            day_events = group["events"]
            break

    html = render_to_string(
        "clinicians/components/_timeline_day.html",
        {"events": day_events, "date": target_date},
        request=request,
    )
    return HttpResponse(html)
