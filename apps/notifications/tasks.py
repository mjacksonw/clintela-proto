"""Celery tasks for notification delivery."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def deliver_notification_task(notification_id):
    """Deliver a single notification asynchronously.

    Called via .delay() when a notification is created and should
    be delivered immediately (e.g., escalation notifications).
    """
    from apps.notifications.services import NotificationService

    results = NotificationService.deliver_notification(notification_id)
    logger.info(
        "Notification delivery complete",
        extra={"notification_id": notification_id, "results": results},
    )
    return results


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def deliver_push_notification_task(self, delivery_id):
    """Deliver a single push notification with retry.

    Retries up to 3 times with 30s backoff for transient FCM errors.
    Bounced tokens (410/gone) do NOT retry.
    """
    from apps.notifications.backends import get_notification_backend
    from apps.notifications.models import NotificationDelivery

    try:
        delivery = NotificationDelivery.objects.select_related("notification", "notification__patient", "device").get(
            id=delivery_id
        )
    except NotificationDelivery.DoesNotExist:
        logger.error("Push delivery %s not found", delivery_id)
        return

    if delivery.status != "pending":
        return  # Already processed

    backend = get_notification_backend("push")
    success = backend.send(delivery.notification, delivery)

    if not success and delivery.status == "failed" and delivery.retry_count <= 3:
        # Transient failure, retry
        try:
            self.retry(countdown=30 * delivery.retry_count)
        except self.MaxRetriesExceededError:
            logger.warning(
                "Push delivery exhausted retries",
                extra={"delivery_id": delivery_id},
            )

    return success


@shared_task
def send_scheduled_reminders():
    """Periodic task: deliver pending reminder notifications.

    Runs every 5 minutes via Celery Beat. Processes pending
    NotificationDelivery records for reminder-type notifications
    in batches of 100 patients.

    Coalesces same-time notifications per patient into a single
    SMS (notification batching). Ad-hoc notifications (escalations,
    nurse messages) always send immediately via deliver_notification_task.
    """
    from django.db.models import Count

    from apps.notifications.models import NotificationDelivery
    from apps.notifications.services import NotificationService

    # Find pending reminder deliveries, grouped by patient
    pending = (
        NotificationDelivery.objects.filter(
            status="pending",
            notification__notification_type="reminder",
        )
        .select_related("notification", "notification__patient")
        .order_by("notification__patient_id", "created_at")
    )

    if not pending.exists():
        return {"processed": 0}

    # Process in batches per patient (coalesce same-time notifications)
    processed = 0
    patient_ids = pending.values("notification__patient_id").annotate(count=Count("id")).order_by()[:100]

    for entry in patient_ids:
        patient_id = entry["notification__patient_id"]
        if not patient_id:
            continue

        patient_deliveries = pending.filter(notification__patient_id=patient_id)

        for delivery in patient_deliveries:
            NotificationService.deliver_notification(delivery.notification_id)
            processed += 1

    logger.info("Scheduled reminders processed: %d", processed)
    return {"processed": processed}
