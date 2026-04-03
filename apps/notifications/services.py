"""Notification service — creates and delivers notifications.

Notification flow:
    create_notification()
    ├── Creates Notification record
    ├── Creates NotificationDelivery per channel (from patient preferences or explicit)
    ├── Pushes notification.new via channel layer (WebSocket)
    └── Returns notification_id for async delivery

    deliver_notification()
    ├── Iterates NotificationDelivery records
    ├── Checks preferences + quiet hours
    ├── Dispatches to backend per channel via get_notification_backend()
    └── Pushes delivery.status_update via channel layer
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.notifications.backends import get_notification_backend
from apps.notifications.models import (
    DeviceToken,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)

logger = logging.getLogger(__name__)

# Threshold for considering a WS session "active" (seconds)
WS_ACTIVE_THRESHOLD = 60

# Max automated SMS per patient per day (care team messages bypass this)
SMS_DAILY_CAP = 5

# Notification types that bypass batching and SMS cap
INSTANT_TYPES = {"escalation"}


def _push_notification_to_websocket(notification):
    """Push a new notification event via channel layer.

    Non-blocking — failures are logged but don't break delivery.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        payload = {
            "id": notification.id,
            "type": notification.notification_type,
            "severity": notification.severity,
            "title": notification.title,
            "message": notification.message,
            "is_read": notification.is_read,
            "created_at": notification.created_at.isoformat() if notification.created_at else "",
        }

        if notification.patient_id:
            group = f"patient_{notification.patient_id}_notifications"
            unread = Notification.objects.filter(patient_id=notification.patient_id, is_read=False).count()
            async_to_sync(channel_layer.group_send)(
                group,
                {
                    "type": "notification.new",
                    "notification": payload,
                    "unread_count": unread,
                },
            )

        if notification.clinician_id:
            group = f"clinician_{notification.clinician_id}_notifications"
            async_to_sync(channel_layer.group_send)(
                group,
                {
                    "type": "notification.new",
                    "notification": payload,
                },
            )
    except Exception:
        logger.debug("Channel layer push failed (non-critical)", exc_info=True)


def _push_delivery_status(notification_id, channel, status):
    """Push delivery status update via channel layer."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        notification = Notification.objects.get(id=notification_id)
        if notification.patient_id:
            group = f"patient_{notification.patient_id}_notifications"
            async_to_sync(channel_layer.group_send)(
                group,
                {
                    "type": "delivery.status_update",
                    "notification_id": notification_id,
                    "channel": channel,
                    "status": status,
                },
            )
    except Exception:
        logger.debug("Delivery status push failed (non-critical)", exc_info=True)


# Default channels when patient has no preferences configured
DEFAULT_CHANNELS = ["in_app"]


class NotificationService:
    """Service for creating and delivering notifications."""

    @staticmethod
    def create_notification(
        patient=None,
        clinician=None,
        notification_type="alert",
        severity="info",
        title="",
        message="",
        channels=None,
    ):
        """Create a notification with delivery records per channel.

        Args:
            patient: Patient instance (optional)
            clinician: Clinician instance (optional)
            notification_type: One of escalation/reminder/alert/update
            severity: One of info/warning/critical
            title: Notification title
            message: Notification body
            channels: List of channels to deliver to.
                      If None, uses patient preferences or DEFAULT_CHANNELS.

        Returns:
            Created Notification instance
        """
        notification = Notification.objects.create(
            patient=patient,
            clinician=clinician,
            notification_type=notification_type,
            severity=severity,
            title=title,
            message=message,
        )

        if channels is None:
            channels = NotificationService._get_channels_for_patient(patient, notification_type)

        # Route through hierarchy if push is enabled
        if getattr(settings, "ENABLE_MOBILE_PUSH", False) and patient:
            channels = NotificationService._route_channels(patient, notification_type, channels)

        for channel in channels:
            if channel == "push" and patient:
                # Fan-out: one delivery per active device token
                NotificationService._create_push_deliveries(notification, patient)
            else:
                NotificationDelivery.objects.create(
                    notification=notification,
                    channel=channel,
                )

        logger.info(
            "Notification created",
            extra={
                "notification_id": notification.id,
                "type": notification_type,
                "severity": severity,
                "channels": channels,
                "patient_id": getattr(patient, "id", None),
            },
        )

        # Push to WebSocket
        _push_notification_to_websocket(notification)

        # Relay to caregivers (if push is enabled and notification is relayable)
        if getattr(settings, "ENABLE_MOBILE_PUSH", False) and patient:
            try:
                from apps.notifications.caregiver_push import relay_to_caregivers

                relay_to_caregivers(notification)
            except Exception:
                logger.debug("Caregiver push relay failed (non-critical)", exc_info=True)

        return notification

    @staticmethod
    def deliver_notification(notification_id):
        """Deliver a notification through all its pending delivery channels.

        Respects preferences and quiet hours. Skips disabled channels
        and defers during quiet hours (marks as pending, not failed).

        Args:
            notification_id: ID of the Notification to deliver

        Returns:
            Dict with delivery results per channel
        """
        try:
            notification = Notification.objects.select_related("patient", "clinician").get(id=notification_id)
        except Notification.DoesNotExist:
            logger.error("Notification %s not found for delivery", notification_id)
            return {}

        deliveries = NotificationDelivery.objects.filter(
            notification=notification,
            status="pending",
        )

        results = {}
        for delivery in deliveries:
            # Check preferences
            if notification.patient and not NotificationService._is_channel_enabled(
                notification.patient, delivery.channel, notification.notification_type
            ):
                delivery.status = "failed"
                delivery.error_message = "Channel disabled by patient preference"
                delivery.save(update_fields=["status", "error_message"])
                results[delivery.channel] = False
                continue

            # Check SMS daily cap (automated messages only)
            if (
                delivery.channel == "sms"
                and notification.patient
                and notification.notification_type not in INSTANT_TYPES
                and not NotificationService._check_sms_cap(notification.patient)
            ):
                logger.info(
                    "SMS delivery deferred (daily cap)",
                    extra={
                        "notification_id": notification_id,
                        "patient_id": notification.patient_id,
                    },
                )
                results[delivery.channel] = None  # Deferred
                continue

            # Check quiet hours
            if notification.patient and NotificationService._is_quiet_hours(
                notification.patient, delivery.channel, notification.notification_type
            ):
                # Leave as pending — will be retried later
                logger.info(
                    "Delivery deferred (quiet hours)",
                    extra={
                        "notification_id": notification_id,
                        "channel": delivery.channel,
                    },
                )
                results[delivery.channel] = None  # None = deferred
                continue

            # Dispatch to backend
            backend = get_notification_backend(delivery.channel)
            try:
                success = backend.send(notification, delivery)
                results[delivery.channel] = success
                if success:
                    _push_delivery_status(notification_id, delivery.channel, delivery.status)
            except Exception:
                logger.exception(
                    "Backend delivery failed",
                    extra={
                        "notification_id": notification_id,
                        "channel": delivery.channel,
                    },
                )
                delivery.status = "failed"
                delivery.retry_count += 1
                delivery.error_message = "Backend raised exception"
                delivery.save(update_fields=["status", "retry_count", "error_message"])
                results[delivery.channel] = False

        return results

    @staticmethod
    def mark_read(notification_id):
        """Mark a notification as read.

        Args:
            notification_id: ID of the Notification
        """
        now = timezone.now()
        Notification.objects.filter(id=notification_id).update(is_read=True, read_at=now)

    @staticmethod
    def get_unread_for_patient(patient_id):
        """Get unread notifications for a patient.

        Args:
            patient_id: Patient ID

        Returns:
            QuerySet of unread Notifications
        """
        return (
            Notification.objects.filter(patient_id=patient_id, is_read=False)
            .prefetch_related("deliveries")
            .order_by("-created_at")
        )

    @staticmethod
    def get_unread_for_clinician(clinician_id):
        """Get unread notifications for a clinician.

        Args:
            clinician_id: Clinician ID

        Returns:
            QuerySet of unread Notifications
        """
        return (
            Notification.objects.filter(clinician_id=clinician_id, is_read=False)
            .prefetch_related("deliveries")
            .order_by("-created_at")
        )

    @staticmethod
    def create_escalation_notification(escalation):
        """Create notification from an escalation event.

        Bridge between EscalationService and NotificationService.
        Creates notifications for both the patient and the assigned clinician.

        Args:
            escalation: Escalation model instance
        """
        severity_map = {
            "critical": "critical",
            "urgent": "warning",
            "high": "warning",
            "routine": "info",
        }

        # Notify patient
        if escalation.patient:
            NotificationService.create_notification(
                patient=escalation.patient,
                notification_type="escalation",
                severity=severity_map.get(escalation.severity, "warning"),
                title="Your care team has been notified",
                message="A member of your care team will follow up with you shortly.",
                channels=["in_app"],  # Escalation patient notice is in-app only
            )

        # Notify clinician (if assigned)
        if hasattr(escalation, "assigned_to") and escalation.assigned_to:
            from apps.clinicians.models import Clinician

            try:
                clinician = Clinician.objects.get(user=escalation.assigned_to)
                NotificationService.create_notification(
                    clinician=clinician,
                    notification_type="escalation",
                    severity=severity_map.get(escalation.severity, "warning"),
                    title=f"Escalation: {escalation.patient.user.get_full_name() if escalation.patient else 'Unknown'}",
                    message=escalation.reason[:500],
                    channels=["in_app", "sms"],
                )
            except Clinician.DoesNotExist:
                logger.warning(
                    "Clinician not found for escalation notification",
                    extra={"user_id": escalation.assigned_to.id},
                )

    @staticmethod
    def _route_channels(patient, notification_type, channels):
        """Apply WS > Push > SMS routing hierarchy.

        Rules:
        - If patient has active WS (last_active_at < 60s), suppress push + SMS
        - If patient has active push tokens, prefer push over SMS
        - If no push tokens (or all bounced), fall back to SMS
        - Conversational (escalation) messages always go through all channels
        """
        if notification_type in INSTANT_TYPES:
            # Escalations bypass routing, send everywhere
            return channels

        # Check WebSocket presence
        if NotificationService._is_ws_active(patient):
            # WS is live, patient is seeing notifications in real time.
            # Keep in_app, suppress push and SMS.
            return [ch for ch in channels if ch not in ("push", "sms")]

        # Check for active push tokens
        has_push_tokens = DeviceToken.objects.filter(patient=patient, is_active=True).exists()

        if has_push_tokens:
            # Replace SMS with push (keep in_app + push, drop SMS)
            result = [ch for ch in channels if ch != "sms"]
            if "push" not in result:
                result.append("push")
            return result

        # No push tokens, fall through to whatever channels were requested
        return channels

    @staticmethod
    def _is_ws_active(patient):
        """Check if patient has an active WebSocket session.

        Uses last_active_at on User model, updated by WS consumer heartbeat.
        Threshold: 60 seconds.
        """
        user = getattr(patient, "user", None)
        if not user:
            return False

        last_active = getattr(user, "last_active_at", None)
        if not last_active:
            return False

        return (timezone.now() - last_active) < timedelta(seconds=WS_ACTIVE_THRESHOLD)

    @staticmethod
    def _create_push_deliveries(notification, patient):
        """Fan-out: create one NotificationDelivery per active device token."""
        active_tokens = DeviceToken.objects.filter(patient=patient, is_active=True)
        for device in active_tokens:
            NotificationDelivery.objects.create(
                notification=notification,
                channel="push",
                device=device,
            )

    @staticmethod
    def _check_sms_cap(patient):
        """Check if patient has hit the daily automated SMS cap.

        Returns True if under cap, False if at or over.
        """
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        sent_today = (
            NotificationDelivery.objects.filter(
                notification__patient=patient,
                channel="sms",
                status__in=["sent", "delivered"],
                created_at__gte=today_start,
            )
            .exclude(
                notification__notification_type__in=INSTANT_TYPES,
            )
            .count()
        )
        return sent_today < SMS_DAILY_CAP

    @staticmethod
    def _get_channels_for_patient(patient, notification_type):
        """Get enabled channels from patient preferences.

        Falls back to DEFAULT_CHANNELS if no preferences exist.
        """
        if not patient:
            return list(DEFAULT_CHANNELS)

        prefs = NotificationPreference.objects.filter(
            patient=patient,
            notification_type=notification_type,
            enabled=True,
        )

        if not prefs.exists():
            return list(DEFAULT_CHANNELS)

        return [p.channel for p in prefs]

    @staticmethod
    def _is_channel_enabled(patient, channel, notification_type):
        """Check if a channel is enabled for this patient/type.

        Returns True if no preference exists (opt-out model).
        """
        try:
            pref = NotificationPreference.objects.get(
                patient=patient,
                channel=channel,
                notification_type=notification_type,
            )
            return pref.enabled
        except NotificationPreference.DoesNotExist:
            return True  # No preference = enabled by default

    @staticmethod
    def _is_quiet_hours(patient, channel, notification_type):
        """Check if current time falls within quiet hours.

        Returns False if no quiet hours configured.
        """
        try:
            pref = NotificationPreference.objects.get(
                patient=patient,
                channel=channel,
                notification_type=notification_type,
            )
        except NotificationPreference.DoesNotExist:
            return False

        if not pref.quiet_hours_start or not pref.quiet_hours_end:
            return False

        now = timezone.localtime().time()
        start = pref.quiet_hours_start
        end = pref.quiet_hours_end

        # Handle overnight quiet hours (e.g., 22:00 - 07:00)
        if start <= end:
            return start <= now <= end
        else:
            return now >= start or now <= end
