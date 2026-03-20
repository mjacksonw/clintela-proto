"""Notification delivery backends.

Backend hierarchy:
    BaseNotificationBackend.send(notification, delivery) -> bool
    ├── InAppBackend         — marks delivered immediately (DB-only)
    ├── ConsoleBackend       — prints formatted notification to stdout
    ├── SMSBackend           — delegates to messages_app SMS backend
    ├── EmailBackend         — delegates to Django's email system
    └── LocMemBackend        — stores in .outbox list (for tests)

Configuration via NOTIFICATION_BACKENDS setting (channel → backend class path).
"""

import importlib
import logging
import sys
from functools import cache

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class BaseNotificationBackend:
    """Abstract base for notification delivery backends."""

    def send(self, notification, delivery):
        """Deliver a notification through this backend.

        Args:
            notification: Notification model instance
            delivery: NotificationDelivery model instance

        Returns:
            True if delivery succeeded, False otherwise.
        """
        raise NotImplementedError


class InAppBackend(BaseNotificationBackend):
    """In-app notification — marks delivered immediately (DB-only)."""

    def send(self, notification, delivery):
        delivery.status = "delivered"
        delivery.delivered_at = timezone.now()
        delivery.save(update_fields=["status", "delivered_at"])
        logger.info(
            "In-app notification delivered",
            extra={"notification_id": notification.id, "patient_id": getattr(notification.patient, "id", None)},
        )
        return True


class ConsoleBackend(BaseNotificationBackend):
    """Prints notification to stdout — for development use."""

    def send(self, notification, delivery):
        severity_icon = {"info": "ℹ", "warning": "⚠", "critical": "🚨"}.get(notification.severity, "•")
        output = (
            f"\n{'═' * 50}\n"
            f"  {severity_icon}  NOTIFICATION ({delivery.channel})\n"
            f"{'─' * 50}\n"
            f"  To:       {notification.patient or notification.clinician}\n"
            f"  Type:     {notification.notification_type}\n"
            f"  Severity: {notification.severity}\n"
            f"  Title:    {notification.title}\n"
            f"  Message:  {notification.message}\n"
            f"{'═' * 50}\n"
        )
        sys.stdout.write(output)
        sys.stdout.flush()

        delivery.status = "delivered"
        delivery.delivered_at = timezone.now()
        delivery.save(update_fields=["status", "delivered_at"])
        return True


class SMSBackend(BaseNotificationBackend):
    """Delegates to messages_app SMS backend for actual SMS delivery."""

    def send(self, notification, delivery):
        if not notification.patient:
            logger.warning(
                "SMS notification skipped — no patient",
                extra={"notification_id": notification.id},
            )
            delivery.status = "failed"
            delivery.error_message = "No patient associated with notification"
            delivery.save(update_fields=["status", "error_message"])
            return False

        phone = getattr(notification.patient.user, "phone_number", None)
        if not phone:
            logger.warning(
                "SMS notification skipped — patient has no phone number",
                extra={"notification_id": notification.id, "patient_id": notification.patient.id},
            )
            delivery.status = "failed"
            delivery.error_message = "Patient has no phone number"
            delivery.save(update_fields=["status", "error_message"])
            return False

        try:
            from apps.messages_app.services import SMSService

            sms_service = SMSService()
            result = sms_service.send_sms(
                patient=notification.patient,
                body=f"{notification.title}: {notification.message}",
                notification=notification,
            )
            delivery.status = "sent"
            delivery.external_id = result.get("sid", "")
            delivery.save(update_fields=["status", "external_id"])
            logger.info(
                "SMS notification sent",
                extra={"notification_id": notification.id, "patient_id": notification.patient.id},
            )
            return True
        except Exception:
            logger.exception(
                "SMS notification failed",
                extra={"notification_id": notification.id, "patient_id": notification.patient.id},
            )
            delivery.status = "failed"
            delivery.retry_count += 1
            delivery.error_message = "SMS send failed"
            delivery.save(update_fields=["status", "retry_count", "error_message"])
            return False


class EmailBackend(BaseNotificationBackend):
    """Delegates to Django's email system."""

    def send(self, notification, delivery):
        recipient = notification.patient or notification.clinician
        if not recipient:
            delivery.status = "failed"
            delivery.error_message = "No recipient for email"
            delivery.save(update_fields=["status", "error_message"])
            return False

        email = getattr(getattr(recipient, "user", None), "email", None)
        if not email:
            delivery.status = "failed"
            delivery.error_message = "Recipient has no email address"
            delivery.save(update_fields=["status", "error_message"])
            return False

        try:
            from django.core.mail import send_mail

            send_mail(
                subject=notification.title,
                message=notification.message,
                from_email=None,  # uses DEFAULT_FROM_EMAIL
                recipient_list=[email],
                fail_silently=False,
            )
            delivery.status = "sent"
            delivery.save(update_fields=["status"])
            logger.info(
                "Email notification sent",
                extra={"notification_id": notification.id},
            )
            return True
        except Exception:
            logger.exception(
                "Email notification failed",
                extra={"notification_id": notification.id},
            )
            delivery.status = "failed"
            delivery.retry_count += 1
            delivery.error_message = "Email send failed"
            delivery.save(update_fields=["status", "retry_count", "error_message"])
            return False


class LocMemBackend(BaseNotificationBackend):
    """In-memory backend for testing. Stores deliveries in .outbox class var."""

    outbox = []

    def send(self, notification, delivery):
        LocMemBackend.outbox.append(
            {
                "notification": notification,
                "delivery": delivery,
                "channel": delivery.channel,
                "title": notification.title,
                "message": notification.message,
            }
        )
        delivery.status = "delivered"
        delivery.delivered_at = timezone.now()
        delivery.save(update_fields=["status", "delivered_at"])
        return True

    @classmethod
    def reset(cls):
        """Clear the outbox. Call in test setUp/tearDown."""
        cls.outbox.clear()


@cache
def _import_backend_class(dotted_path):
    """Import a backend class from a dotted path string."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_notification_backend(channel):
    """Get the notification backend instance for a given channel.

    Reads from settings.NOTIFICATION_BACKENDS, a dict mapping
    channel names to dotted class paths.

    Args:
        channel: One of 'in_app', 'sms', 'email'

    Returns:
        BaseNotificationBackend instance
    """
    backends = getattr(settings, "NOTIFICATION_BACKENDS", {})
    dotted_path = backends.get(channel)

    if not dotted_path:
        logger.warning("No notification backend configured for channel=%s, falling back to ConsoleBackend", channel)
        return ConsoleBackend()

    backend_class = _import_backend_class(dotted_path)
    return backend_class()
