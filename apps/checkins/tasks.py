"""
Celery tasks for daily check-in scheduling and lifecycle.

Key patterns:
- send_daily_checkins dispatches per-patient subtasks (spreads load)
- send_patient_checkin is idempotent (guards against duplicate widget messages)
- expire_missed_checkins marks incomplete sessions and grays out widgets
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="checkins.send_daily_checkins")
def send_daily_checkins():
    """Daily task: dispatch per-patient check-in subtasks.

    Runs once daily (via Celery beat). For each active patient with a pathway,
    dispatches send_patient_checkin as a subtask.
    """
    from apps.pathways.models import PatientPathway

    active_pathways = PatientPathway.objects.filter(status="active").select_related("patient")

    dispatched = 0
    for pp in active_pathways:
        send_patient_checkin.delay(pp.patient_id)
        dispatched += 1

    logger.info("Dispatched %d check-in tasks", dispatched)
    return {"dispatched": dispatched}


@shared_task(name="checkins.send_patient_checkin", bind=True, max_retries=2)
def send_patient_checkin(self, patient_id):
    """Per-patient check-in creation with idempotency guard.

    Guard: if session exists for today AND has widget AgentMessages,
    skip the send step (handles Celery retry safety).
    """
    from apps.agents.models import AgentMessage
    from apps.checkins.models import CheckinSession
    from apps.checkins.selection import _patient_today
    from apps.checkins.services import CheckinService
    from apps.patients.models import Patient

    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        logger.warning("Patient %s not found, skipping check-in", patient_id)
        return {"status": "skipped", "reason": "patient_not_found"}

    # Quiet hours check
    if _is_quiet_hours(patient):
        logger.debug("Quiet hours for patient %s, skipping", patient_id)
        return {"status": "deferred", "reason": "quiet_hours"}

    today = _patient_today(patient)

    # Idempotency guard: check if session already has widget messages
    existing_session = CheckinSession.objects.filter(
        patient=patient,
        date=today,
    ).first()

    if existing_session:
        has_widgets = AgentMessage.objects.filter(
            conversation=existing_session.conversation,
            metadata__type="checkin_widget",
            metadata__session_id=str(existing_session.id),
        ).exists()

        if has_widgets:
            logger.info("Session %s already has widgets, skipping", existing_session.id)
            return {"status": "skipped", "reason": "already_sent"}

    try:
        session = CheckinService.create_daily_session(patient)
        if session:
            return {"status": "sent", "session_id": str(session.id)}
        return {"status": "skipped", "reason": "no_questions_selected"}
    except Exception as exc:
        logger.exception("Failed to create check-in for patient %s", patient_id)
        raise self.retry(exc=exc, countdown=60) from exc


@shared_task(name="checkins.expire_missed_checkins")
def expire_missed_checkins():
    """Mark incomplete sessions from previous days as missed.

    Updates AgentMessage metadata to show expired state
    (widgets render grayed out, not disappearing).
    """
    from apps.agents.models import AgentMessage
    from apps.checkins.models import CheckinSession
    from apps.checkins.widgets import update_widget_expired

    today = timezone.now().date()

    missed_sessions = CheckinSession.objects.filter(
        date__lt=today,
        status__in=["pending", "in_progress"],
    )

    count = 0
    for session in missed_sessions:
        session.status = "missed"
        session.save(update_fields=["status"])

        # Update widget messages to expired state
        widget_messages = AgentMessage.objects.filter(
            metadata__type="checkin_widget",
            metadata__session_id=str(session.id),
        )

        for msg in widget_messages:
            if not msg.metadata.get("expired"):
                msg.metadata = update_widget_expired(msg.metadata)
                msg.save(update_fields=["metadata"])

        count += 1

    if count:
        logger.info("Expired %d missed check-in sessions", count)
    return {"expired": count}


def _is_quiet_hours(patient):
    """Check if it's currently quiet hours for this patient."""
    try:
        import zoneinfo

        from apps.notifications.models import NotificationPreference

        pref = NotificationPreference.objects.filter(patient=patient).first()
        if not pref:
            return False

        # Get current time in patient's timezone
        tz_name = pref.timezone or "America/New_York"
        tz = zoneinfo.ZoneInfo(tz_name)
        now_local = timezone.now().astimezone(tz).time()

        start = pref.quiet_hours_start
        end = pref.quiet_hours_end

        if not start or not end:
            return False

        # Handle overnight quiet hours (e.g., 21:00 to 08:00)
        if start > end:
            return now_local >= start or now_local <= end
        else:
            return start <= now_local <= end

    except Exception:
        logger.debug("Quiet hours check failed for patient %s", patient.id)
        return False
