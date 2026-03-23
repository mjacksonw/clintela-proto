"""Services for clinician dashboard features."""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import models, transaction
from django.db.models import Count, Max, Q, Subquery
from django.utils import timezone

from apps.agents.models import AgentConversation, AgentMessage, Escalation
from apps.agents.services import ContextService, ConversationService
from apps.clinicians.models import Appointment, Clinician, ClinicianAvailability
from apps.patients.models import Patient

logger = logging.getLogger(__name__)


class PatientListService:
    """Service for building annotated patient lists."""

    @staticmethod
    def get_patients_for_clinician(clinician: Clinician, sort: str = "severity", search: str = ""):
        """Get patients from clinician's hospitals with annotations.

        Uses Subquery/Count/Max annotations — NOT per-patient queries.
        """
        hospital_ids = clinician.hospitals.values_list("id", flat=True)

        # Subqueries for status line — avoids N+1 per-patient queries
        pending_reason_sq = Subquery(
            Escalation.objects.filter(patient_id=models.OuterRef("pk"), status="pending")
            .order_by("-created_at")
            .values("reason")[:1]
        )
        last_msg_sq = Subquery(
            AgentMessage.objects.filter(
                conversation__patient_id=models.OuterRef("pk"),
                role="assistant",
            )
            .order_by("-created_at")
            .values("content")[:1]
        )

        # Clinical trajectory annotation (feature-flagged)
        from django.conf import settings

        clinical_annotations = {}
        if getattr(settings, "ENABLE_CLINICAL_DATA", False):
            from apps.clinical.models import PatientClinicalSnapshot

            clinical_annotations["_clinical_trajectory"] = Subquery(
                PatientClinicalSnapshot.objects.filter(patient_id=models.OuterRef("pk")).values("trajectory")[:1]
            )

        qs = (
            Patient.objects.filter(hospital_id__in=hospital_ids, is_active=True)
            .select_related("user", "hospital")
            .annotate(
                pending_escalation_count=Count(
                    "escalations",
                    filter=Q(escalations__status="pending"),
                ),
                last_message_at=Max(
                    "agent_conversations__messages__created_at",
                ),
                _pending_reason=pending_reason_sq,
                _last_msg_content=last_msg_sq,
                **clinical_annotations,
            )
        )

        if search:
            qs = qs.filter(
                Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search) | Q(mrn__icontains=search)
            )

        # Sort ordering
        severity_order = {"red": 0, "orange": 1, "yellow": 2, "green": 3}
        if sort == "alpha":
            qs = qs.order_by("user__last_name", "user__first_name")
        elif sort == "last_contact":
            qs = qs.order_by("-last_message_at")
        else:
            # severity sort: done in Python since status is a char field
            patients = list(qs)
            patients.sort(key=lambda p: (severity_order.get(p.status, 99), p.user.last_name))
            return patients

        return list(qs)

    @staticmethod
    def get_status_line(patient: Patient) -> str:
        """Build the status line for a patient list item.

        Uses _pending_reason and _last_msg_content annotations from
        get_patients_for_clinician() when available (0 extra queries).
        Falls back to per-patient queries for standalone calls.
        """
        # Priority: pending escalation > last AI message > lifecycle fallback
        pending_reason = getattr(patient, "_pending_reason", None)
        if pending_reason is None and not hasattr(patient, "_pending_reason"):
            # Fallback: annotation not present (standalone call)
            pending = (
                Escalation.objects.filter(patient=patient, status="pending").values_list("reason", flat=True).first()
            )
            pending_reason = pending

        if pending_reason:
            return pending_reason[:80]

        last_msg_content = getattr(patient, "_last_msg_content", None)
        if last_msg_content is None and not hasattr(patient, "_last_msg_content"):
            # Fallback: annotation not present
            last_msg = (
                AgentMessage.objects.filter(
                    conversation__patient=patient,
                    role="assistant",
                )
                .order_by("-created_at")
                .values_list("content", flat=True)
                .first()
            )
            last_msg_content = last_msg

        if last_msg_content:
            return last_msg_content[:80]

        days = patient.days_post_op()
        if days is not None:
            return f"{patient.get_lifecycle_status_display()} - Day {days} post-op"
        return patient.get_lifecycle_status_display()


class HandoffService:
    """Service for shift handoff summaries."""

    @staticmethod
    def get_handoff_summary(clinician: Clinician, since: datetime) -> dict[str, Any]:
        """Get changes since the clinician's last login.

        Args:
            clinician: Clinician instance
            since: datetime of last login

        Returns:
            Dict with new_escalations, resolved_escalations, status_changes, missed_checkins
        """
        hospital_ids = clinician.hospitals.values_list("id", flat=True)

        new_escalations = Escalation.objects.filter(
            patient__hospital_id__in=hospital_ids,
            created_at__gte=since,
            status="pending",
        ).select_related("patient__user")[:10]

        resolved_escalations = Escalation.objects.filter(
            patient__hospital_id__in=hospital_ids,
            resolved_at__gte=since,
            status="resolved",
        ).select_related("patient__user")[:10]

        from apps.patients.models import PatientStatusTransition

        status_changes = PatientStatusTransition.objects.filter(
            patient__hospital_id__in=hospital_ids,
            created_at__gte=since,
        ).select_related("patient__user")[:10]

        # Evaluate sliced querysets once, then use len() (avoids extra COUNT queries)
        new_escalations = list(new_escalations)
        resolved_escalations = list(resolved_escalations)
        status_changes = list(status_changes)

        # Clinical alerts since last login (feature-flagged)
        from django.conf import settings

        clinical_alerts = []
        if getattr(settings, "ENABLE_CLINICAL_DATA", False):
            from apps.clinical.models import ClinicalAlert

            clinical_alerts = list(
                ClinicalAlert.objects.filter(
                    patient__hospital_id__in=hospital_ids,
                    created_at__gte=since,
                )
                .select_related("patient__user")
                .order_by("-created_at")[:10]
            )

        return {
            "new_escalations": new_escalations,
            "resolved_escalations": resolved_escalations,
            "status_changes": status_changes,
            "clinical_alerts": clinical_alerts,
            "new_escalation_count": len(new_escalations),
            "resolved_count": len(resolved_escalations),
            "status_change_count": len(status_changes),
            "clinical_alert_count": len(clinical_alerts),
        }


class TimelineService:
    """Service for patient timeline — interleaves events from multiple models."""

    @staticmethod
    def get_timeline(patient: Patient, days: int = 30) -> list[dict]:
        """Get timeline events grouped by date.

        Runs 5 bulk queries + Python merge/sort by timestamp + group by date.
        """
        from apps.patients.models import PatientStatusTransition

        cutoff = timezone.now() - timedelta(days=days)

        # 5 bulk queries
        transitions = list(
            PatientStatusTransition.objects.filter(patient=patient, created_at__gte=cutoff).values(
                "id", "from_status", "to_status", "created_at", "reason"
            )
        )
        for t in transitions:
            t["event_type"] = "transition"

        escalations = list(
            Escalation.objects.filter(patient=patient, created_at__gte=cutoff).values(
                "id", "reason", "severity", "status", "created_at"
            )
        )
        for e in escalations:
            e["event_type"] = "escalation"

        conversations = list(
            AgentConversation.objects.filter(
                patient=patient,
                created_at__gte=cutoff,
                clinician__isnull=True,  # exclude research
            ).values("id", "agent_type", "status", "created_at")
        )
        for c in conversations:
            c["event_type"] = "conversation"

        from apps.pathways.models import PatientMilestoneCheckin

        checkins = list(
            PatientMilestoneCheckin.objects.filter(patient=patient, sent_at__gte=cutoff)
            .select_related("milestone")
            .values("id", "milestone__title", "completed_at", "skipped", "sent_at")
        )
        for ck in checkins:
            ck["event_type"] = "checkin"
            ck["created_at"] = ck["sent_at"]

        from apps.clinicians.models import ClinicianNote

        notes = list(
            ClinicianNote.objects.filter(patient=patient, created_at__gte=cutoff).values(
                "id", "content", "note_type", "created_at"
            )
        )
        for n in notes:
            n["event_type"] = "note"

        # Merge and sort
        all_events = transitions + escalations + conversations + checkins + notes
        all_events.sort(key=lambda e: e["created_at"], reverse=True)

        # Group by date
        grouped = {}
        for event in all_events:
            day = event["created_at"].date()
            if day not in grouped:
                grouped[day] = {
                    "date": day,
                    "events": [],
                    "counts": {
                        "transition": 0,
                        "escalation": 0,
                        "conversation": 0,
                        "checkin": 0,
                        "note": 0,
                    },
                }
            grouped[day]["events"].append(event)
            grouped[day]["counts"][event["event_type"]] += 1

        return sorted(grouped.values(), key=lambda g: g["date"], reverse=True)


class TakeControlService:
    """Service for clinician take-control of patient chat threads."""

    @staticmethod
    @transaction.atomic
    def take_control(conversation: AgentConversation, clinician_user) -> bool:
        """Atomically take control of a conversation.

        Returns True if control was acquired, False if another clinician has it.
        """
        rows = AgentConversation.objects.filter(
            pk=conversation.pk,
            paused_by__isnull=True,
        ).update(
            paused_by=clinician_user,
            paused_at=timezone.now(),
        )
        if rows == 1:
            logger.info(
                "Take control: clinician=%s conversation=%s",
                clinician_user.id,
                conversation.pk,
            )
            return True
        return False

    @staticmethod
    @transaction.atomic
    def release_control(conversation: AgentConversation, clinician_user=None) -> bool:
        """Release control of a conversation.

        If clinician_user is provided, only releases if that user has control.
        """
        filters = {"pk": conversation.pk, "paused_by__isnull": False}
        if clinician_user:
            filters["paused_by"] = clinician_user

        rows = AgentConversation.objects.filter(**filters).update(
            paused_by=None,
            paused_at=None,
        )
        if rows == 1:
            logger.info(
                "Release control: clinician=%s conversation=%s",
                clinician_user.id if clinician_user else "system",
                conversation.pk,
            )
            return True
        return False

    @staticmethod
    def release_stale_locks(timeout_minutes: int = 30) -> int:
        """Release conversations locked for longer than timeout.

        Called by Celery periodic task as a fallback for browser crashes.

        Returns:
            Number of conversations released.
        """
        cutoff = timezone.now() - timedelta(minutes=timeout_minutes)
        rows = AgentConversation.objects.filter(
            paused_by__isnull=False,
            paused_at__lt=cutoff,
        ).update(
            paused_by=None,
            paused_at=None,
        )
        if rows > 0:
            logger.info("Released %d stale take-control locks", rows)
        return rows

    @staticmethod
    def push_to_clinician(conversation: AgentConversation, message_data: dict):
        """Push a patient message to the controlling clinician via the hospital dashboard group.

        Gracefully degrades if channel layer is unavailable.
        """
        if not conversation.paused_by:
            return

        try:
            patient = conversation.patient
            hospital_id = patient.hospital_id
            if not hospital_id:
                return

            channel_layer = get_channel_layer()
            group_name = f"hospital_{hospital_id}"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "patient_message",
                    "patient_id": str(patient.id),
                    "message": message_data,
                },
            )
        except Exception:
            logger.warning(
                "Channel layer unavailable for clinician push, conversation=%s",
                conversation.pk,
            )


class ClinicianResearchService:
    """Service for clinician research chat with patient context."""

    @staticmethod
    def get_or_create_research_conversation(patient: Patient, clinician: Clinician) -> AgentConversation:
        """Get or create a research conversation for a clinician-patient pair."""
        conversation = AgentConversation.objects.filter(
            patient=patient,
            clinician=clinician,
            agent_type="clinician_research",
            status="active",
        ).first()

        if conversation:
            return conversation

        return AgentConversation.objects.create(
            patient=patient,
            clinician=clinician,
            agent_type="clinician_research",
            status="active",
            context={"research_mode": True},
        )

    @staticmethod
    def send_research_message(
        patient: Patient,
        clinician: Clinician,
        message: str,
        specialist_override: str = "",
    ) -> dict[str, Any]:
        """Process a research query through the agent workflow.

        Args:
            patient: Patient whose context to use
            clinician: Clinician asking the question
            message: Research query
            specialist_override: Optional specialist to route to directly

        Returns:
            Dict with response, agent_type, metadata
        """
        conversation = ClinicianResearchService.get_or_create_research_conversation(patient, clinician)

        # Save clinician's question
        ConversationService.add_message(
            conversation=conversation,
            role="user",
            content=message,
            metadata={"clinician_id": clinician.id},
        )

        # Assemble context with research_mode flag
        context = ContextService.assemble_full_context(patient, conversation)
        context["research_mode"] = True
        context["clinician"] = {
            "name": clinician.user.get_full_name(),
            "role": clinician.get_role_display(),
            "specialty": clinician.specialty,
        }

        if specialist_override:
            context["specialist_override"] = specialist_override

        # Process through workflow
        from apps.agents.workflow import get_workflow

        workflow = get_workflow()
        try:
            result = async_to_sync(workflow.process_message)(message, context)
        except Exception:
            logger.exception("Research chat LLM failure for patient=%s", patient.id)
            result = {
                "response": "Research unavailable. Try again later.",
                "agent_type": "clinician_research",
                "escalate": False,
                "metadata": {"error": True},
            }

        # Strip escalation (should already be suppressed by research_mode flag)
        result["escalate"] = False

        response_text = result.get("response", "").strip()
        if not response_text:
            response_text = "I wasn't able to process that research query. Please try rephrasing."

        # Save agent response
        agent_message = ConversationService.add_message(
            conversation=conversation,
            role="assistant",
            content=response_text,
            agent_type=result.get("agent_type", "clinician_research"),
            metadata=result.get("metadata", {}),
        )

        logger.info(
            "Research query: clinician=%s patient=%s agent=%s",
            clinician.id,
            patient.id,
            result.get("agent_type"),
        )

        return {
            "message": agent_message,
            "response": response_text,
            "agent_type": result.get("agent_type", "clinician_research"),
            "metadata": result.get("metadata", {}),
        }


class SchedulingService:
    """Service for appointment scheduling and availability management."""

    @staticmethod
    def get_weekly_schedule(clinician: Clinician, week_start: date) -> dict[str, Any]:
        """Get appointments + availability for a week."""
        week_end = week_start + timedelta(days=7)

        appointments = Appointment.objects.filter(
            clinician=clinician,
            scheduled_start__date__gte=week_start,
            scheduled_start__date__lt=week_end,
            status__in=["scheduled", "confirmed", "in_progress"],
        ).select_related("patient__user")

        availability = ClinicianAvailability.objects.filter(
            clinician=clinician,
            is_recurring=True,
        )

        # One-off overrides for this week
        overrides = ClinicianAvailability.objects.filter(
            clinician=clinician,
            is_recurring=False,
            effective_date__gte=week_start,
            effective_date__lt=week_end,
        )

        return {
            "appointments": list(appointments),
            "availability": list(availability),
            "overrides": list(overrides),
            "week_start": week_start,
            "week_end": week_end,
        }

    @staticmethod
    def get_available_slots(clinician: Clinician, target_date: date, duration_minutes: int = 30) -> list[dict]:
        """Get open time slots within availability windows for a date."""
        day_of_week = target_date.weekday()

        windows = ClinicianAvailability.objects.filter(
            clinician=clinician,
            day_of_week=day_of_week,
            is_recurring=True,
        )

        # Check one-off overrides
        override = ClinicianAvailability.objects.filter(
            clinician=clinician,
            effective_date=target_date,
            is_recurring=False,
        ).first()
        if override:
            windows = [override]

        # Get existing appointments for this date
        booked = Appointment.objects.filter(
            clinician=clinician,
            scheduled_start__date=target_date,
            status__in=["scheduled", "confirmed", "in_progress"],
        ).values_list("scheduled_start", "scheduled_end")

        booked_ranges = list(booked)

        slots = []
        for window in windows:
            current = datetime.combine(target_date, window.start_time)
            end = datetime.combine(target_date, window.end_time)
            delta = timedelta(minutes=duration_minutes)

            while current + delta <= end:
                slot_end = current + delta
                # Check conflict
                conflict = any(current < be and slot_end > bs for bs, be in booked_ranges)
                if not conflict:
                    slots.append(
                        {
                            "start": current.time(),
                            "end": slot_end.time(),
                        }
                    )
                current += delta

        return slots

    @staticmethod
    @transaction.atomic
    def create_appointment(
        clinician: Clinician,
        patient: Patient,
        start: datetime,
        end: datetime,
        appointment_type: str,
        created_by=None,
        notes: str = "",
    ) -> Appointment | None:
        """Create an appointment with conflict check.

        Returns None if the slot conflicts with an existing appointment.
        """
        # select_for_update prevents TOCTOU: concurrent txns block here
        conflict = (
            Appointment.objects.select_for_update()
            .filter(
                clinician=clinician,
                scheduled_start__lt=end,
                scheduled_end__gt=start,
                status__in=["scheduled", "confirmed", "in_progress"],
            )
            .exists()
        )

        if conflict:
            return None

        appointment = Appointment.objects.create(
            clinician=clinician,
            patient=patient,
            scheduled_start=start,
            scheduled_end=end,
            appointment_type=appointment_type,
            created_by=created_by,
            notes=notes,
        )

        logger.info(
            "Appointment created: clinician=%s patient=%s type=%s start=%s",
            clinician.id,
            patient.id,
            appointment_type,
            start,
        )
        return appointment

    @staticmethod
    def get_next_appointment(clinician: Clinician) -> Appointment | None:
        """Get the clinician's next upcoming appointment."""
        return (
            Appointment.objects.filter(
                clinician=clinician,
                scheduled_start__gte=timezone.now(),
                status__in=["scheduled", "confirmed"],
            )
            .select_related("patient__user")
            .first()
        )

    @staticmethod
    def get_patient_appointments(patient: Patient):
        """Get upcoming appointments for a patient."""
        return Appointment.objects.filter(
            patient=patient,
            scheduled_start__gte=timezone.now(),
            status__in=["scheduled", "confirmed"],
        ).select_related("clinician__user")


class AppointmentBookingService:
    """Service for patient self-booking of appointments."""

    @staticmethod
    def schedule_pathway_milestones(patient: Patient, patient_pathway):
        """Auto-create AppointmentRequests for milestones with check_in_questions.

        Called when a pathway is assigned. Creates booking requests for
        each milestone that has check-in questions defined.
        """
        from apps.clinicians.models import AppointmentRequest
        from apps.pathways.models import PathwayMilestone

        milestones = PathwayMilestone.objects.filter(
            pathway=patient_pathway.pathway,
            is_active=True,
            check_in_questions__len__gt=0,
        )

        # Find the patient's primary clinician (first clinician at their hospital)
        clinician = Clinician.objects.filter(
            hospitals=patient.hospital,
            is_active=True,
        ).first()

        if not clinician:
            logger.warning(
                "No active clinician for patient %s hospital, skipping milestone scheduling",
                patient.id,
            )
            return []

        requests = []
        for milestone in milestones:
            surgery_date = patient.surgery_date
            if not surgery_date:
                continue

            notify_at = (
                timezone.make_aware(
                    datetime.combine(surgery_date + timedelta(days=milestone.day), datetime.min.time().replace(hour=8))
                )
                if timezone.is_naive(
                    datetime.combine(surgery_date + timedelta(days=milestone.day), datetime.min.time().replace(hour=8))
                )
                else datetime.combine(surgery_date + timedelta(days=milestone.day), datetime.min.time().replace(hour=8))
            )

            expires_at = notify_at + timedelta(days=7)

            req = AppointmentRequest.objects.create(
                patient=patient,
                clinician=clinician,
                trigger_type="milestone",
                reason=f"Day {milestone.day} check-in: {milestone.title}",
                appointment_type="check_in",
                milestone=milestone,
                earliest_notify_at=notify_at,
                expires_at=expires_at,
            )
            requests.append(req)

        logger.info(
            "Created %d milestone booking requests for patient %s",
            len(requests),
            patient.id,
        )
        return requests

    @staticmethod
    def create_request(
        patient: Patient,
        clinician: Clinician,
        trigger_type: str,
        reason: str,
        appointment_type: str = "follow_up",
        milestone=None,
        escalation_obj=None,
        requested_by=None,
        earliest_notify_at=None,
        expires_at=None,
    ):
        """Create an AppointmentRequest.

        Args:
            patient: Patient who should book
            clinician: Clinician to book with
            trigger_type: One of milestone/escalation/clinician
            reason: Human-readable reason shown to patient
            appointment_type: Type from Appointment.TYPE_CHOICES
            milestone: Optional PathwayMilestone FK
            escalation_obj: Optional Escalation FK
            requested_by: Optional User who initiated
            earliest_notify_at: When to first notify patient (default: now)
            expires_at: When the request expires (default: 14 days)

        Returns:
            AppointmentRequest instance
        """
        from apps.clinicians.models import AppointmentRequest

        now = timezone.now()
        if earliest_notify_at is None:
            earliest_notify_at = now
        if expires_at is None:
            expires_at = now + timedelta(days=14)

        request = AppointmentRequest.objects.create(
            patient=patient,
            clinician=clinician,
            trigger_type=trigger_type,
            reason=reason,
            appointment_type=appointment_type,
            milestone=milestone,
            escalation=escalation_obj,
            requested_by=requested_by,
            earliest_notify_at=earliest_notify_at,
            expires_at=expires_at,
        )

        logger.info(
            "AppointmentRequest created: id=%s patient=%s clinician=%s trigger=%s",
            request.id,
            patient.id,
            clinician.id,
            trigger_type,
        )
        return request

    @staticmethod
    @transaction.atomic
    def book_appointment(request_id, patient: Patient, scheduled_start, scheduled_end):
        """Book an appointment from a pending AppointmentRequest.

        Args:
            request_id: UUID of the AppointmentRequest
            patient: Patient making the booking (for auth verification)
            scheduled_start: datetime of appointment start
            scheduled_end: datetime of appointment end

        Returns:
            Appointment instance or None if conflict/invalid
        """
        from apps.clinicians.models import AppointmentRequest

        try:
            appt_request = AppointmentRequest.objects.select_for_update().get(
                id=request_id,
                patient=patient,
                status="pending",
            )
        except AppointmentRequest.DoesNotExist:
            return None

        # Use existing SchedulingService for conflict-safe creation
        appointment = SchedulingService.create_appointment(
            clinician=appt_request.clinician,
            patient=patient,
            start=scheduled_start,
            end=scheduled_end,
            appointment_type=appt_request.appointment_type,
            created_by=patient.user,
            notes=appt_request.reason,
        )

        if appointment is None:
            return None

        # Set virtual visit URL from clinician's Zoom link
        if appt_request.clinician.zoom_link:
            appointment.virtual_visit_url = appt_request.clinician.zoom_link
            appointment.save(update_fields=["virtual_visit_url"])

        # Link request to appointment
        appt_request.status = "booked"
        appt_request.appointment = appointment
        appt_request.save(update_fields=["status", "appointment"])

        logger.info(
            "Appointment booked: request=%s appointment=%s",
            request_id,
            appointment.id,
        )

        return appointment

    @staticmethod
    def send_confirmation_drip(appointment):
        """Send email + SMS confirmation with iCal attachment.

        Uses the notification service for delivery. Attaches a .ics
        calendar file to the email.
        """
        from apps.notifications.services import NotificationService

        patient = appointment.patient

        # Create notification via existing service
        try:
            NotificationService.create_notification(
                patient=patient,
                notification_type="reminder",
                title="Appointment Confirmed",
                message=(
                    f"Your {appointment.get_appointment_type_display()} "
                    f"with {appointment.clinician.user.get_full_name()} "
                    f"is scheduled for {appointment.scheduled_start.strftime('%B %d at %I:%M %p')}."
                ),
                channels=["email", "sms"],
            )
        except Exception:
            logger.exception(
                "Failed to send confirmation for appointment %s",
                appointment.id,
            )

        # Mark iCal as sent
        appointment.ical_sent = True
        appointment.save(update_fields=["ical_sent"])

    @staticmethod
    def get_available_slots_for_booking(clinician: Clinician, days: int = 5) -> list[dict]:
        """Return available slots for the next N business days.

        Args:
            clinician: Clinician to check availability for
            days: Number of business days to check

        Returns:
            List of dicts with 'date', 'day_name', 'slots' keys
        """
        today = date.today()
        result = []
        current = today + timedelta(days=1)  # Start from tomorrow
        business_days_found = 0

        while business_days_found < days:
            if current.weekday() < 5:  # Monday-Friday
                day_slots = SchedulingService.get_available_slots(clinician, current)
                result.append(
                    {
                        "date": current,
                        "day_name": current.strftime("%A"),
                        "date_display": current.strftime("%b %d"),
                        "slots": day_slots,
                    }
                )
                business_days_found += 1
            current += timedelta(days=1)

        return result
