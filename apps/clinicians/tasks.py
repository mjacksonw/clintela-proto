"""Celery tasks for appointment reminders and booking notifications."""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def send_appointment_reminders():
    """Periodic task: send 24h and 1h appointment reminders.

    Runs every 15 minutes via Celery Beat. Checks for upcoming
    appointments that need reminder notifications sent.
    """
    from apps.clinicians.models import Appointment
    from apps.notifications.services import NotificationService

    now = timezone.now()
    processed = 0

    # 24-hour reminders
    window_24h_start = now + timedelta(hours=23, minutes=45)
    window_24h_end = now + timedelta(hours=24, minutes=15)

    appointments_24h = Appointment.objects.filter(
        scheduled_start__gte=window_24h_start,
        scheduled_start__lte=window_24h_end,
        status__in=["scheduled", "confirmed"],
        reminder_24h_sent=False,
    ).select_related("patient", "clinician__user")

    for appointment in appointments_24h:
        try:
            NotificationService.create_notification(
                patient=appointment.patient,
                notification_type="reminder",
                title="Appointment Tomorrow",
                message=(
                    f"Reminder: You have a {appointment.get_appointment_type_display()} "
                    f"with {appointment.clinician.user.get_full_name()} "
                    f"tomorrow at {appointment.scheduled_start.strftime('%I:%M %p')}."
                ),
                channels=["sms", "email"],
            )
            appointment.reminder_24h_sent = True
            appointment.save(update_fields=["reminder_24h_sent"])
            processed += 1
        except Exception:
            logger.exception(
                "Failed to send 24h reminder for appointment %s",
                appointment.id,
            )

    # 1-hour reminders
    window_1h_start = now + timedelta(minutes=45)
    window_1h_end = now + timedelta(hours=1, minutes=15)

    appointments_1h = Appointment.objects.filter(
        scheduled_start__gte=window_1h_start,
        scheduled_start__lte=window_1h_end,
        status__in=["scheduled", "confirmed"],
        reminder_1h_sent=False,
    ).select_related("patient", "clinician__user")

    for appointment in appointments_1h:
        try:
            join_msg = ""
            if appointment.virtual_visit_url:
                join_msg = f" Join here: {appointment.virtual_visit_url}"

            NotificationService.create_notification(
                patient=appointment.patient,
                notification_type="reminder",
                title="Appointment Starting Soon",
                message=(
                    f"Your {appointment.get_appointment_type_display()} "
                    f"with {appointment.clinician.user.get_full_name()} "
                    f"starts in about 1 hour.{join_msg}"
                ),
                channels=["sms"],
            )
            appointment.reminder_1h_sent = True
            appointment.save(update_fields=["reminder_1h_sent"])
            processed += 1
        except Exception:
            logger.exception(
                "Failed to send 1h reminder for appointment %s",
                appointment.id,
            )

    logger.info("Appointment reminders sent: %d", processed)
    return {"processed": processed}


@shared_task
def expire_appointment_requests():
    """Periodic task: expire old pending appointment requests.

    Runs daily at 3:17 AM via Celery Beat. Marks pending requests
    past their expires_at as expired.
    """
    from apps.clinicians.models import AppointmentRequest

    now = timezone.now()
    expired_count = AppointmentRequest.objects.filter(
        status="pending",
        expires_at__lt=now,
    ).update(status="expired")

    if expired_count > 0:
        logger.info("Expired %d appointment requests", expired_count)

    return {"expired": expired_count}


@shared_task
def notify_upcoming_appointments():
    """Periodic task: send booking notifications for pending requests.

    Runs daily at 8:03 AM via Celery Beat. Finds AppointmentRequests
    whose earliest_notify_at has arrived and sends the patient a
    notification to book their appointment.
    """
    from apps.clinicians.models import AppointmentRequest
    from apps.notifications.services import NotificationService

    now = timezone.now()
    notified = 0

    pending_requests = AppointmentRequest.objects.filter(
        status="pending",
        earliest_notify_at__lte=now,
    ).select_related("patient", "clinician__user")

    for req in pending_requests:
        try:
            clinician_name = req.clinician.user.get_full_name()
            NotificationService.create_notification(
                patient=req.patient,
                notification_type="reminder",
                title="Time to Book Your Appointment",
                message=(
                    f"It's time to schedule your {req.get_appointment_type_display()} "
                    f"with {clinician_name}. {req.reason}"
                ),
                channels=["sms", "email"],
            )
            notified += 1
        except Exception:
            logger.exception(
                "Failed to notify for appointment request %s",
                req.id,
            )

    logger.info("Booking notifications sent: %d", notified)
    return {"notified": notified}
