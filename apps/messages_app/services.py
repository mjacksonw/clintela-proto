"""SMS service — send/receive SMS and manage opt-outs.

SMS flow (inbound):
    Twilio webhook → handle_inbound_sms()
    ├── Lookup patient by phone number
    ├── Check for STOP/START keywords
    ├── Create Message record (inbound)
    ├── Call process_patient_message() (shared AI workflow)
    └── Send response SMS (outbound)

SMS flow (outbound):
    send_sms()
    ├── Check ENABLE_SMS + opt-out + rate limit
    ├── Delegate to SMS backend
    └── Create Message record (outbound)
"""

import logging

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from apps.messages_app.backends import get_sms_backend

logger = logging.getLogger(__name__)

STOP_KEYWORDS = {"stop", "unsubscribe", "cancel", "end", "quit"}
START_KEYWORDS = {"start", "subscribe", "unstop"}


class SMSService:
    """Service for SMS sending and receiving."""

    def send_sms(self, patient, body, notification=None):
        """Send an SMS to a patient.

        Args:
            patient: Patient instance
            body: Message text
            notification: Optional Notification instance for correlation

        Returns:
            Dict with 'sid' and 'status'

        Raises:
            ValueError: If SMS is disabled or patient has no phone
        """
        if not getattr(settings, "ENABLE_SMS", False) and not settings.DEBUG:
            raise ValueError("SMS is disabled (ENABLE_SMS=False)")

        phone = getattr(patient.user, "phone_number", None)
        if not phone:
            raise ValueError(f"Patient {patient.id} has no phone number")

        # Check opt-out
        if self._is_opted_out(patient):
            logger.info(
                "SMS skipped — patient opted out",
                extra={"patient_id": patient.id},
            )
            return {"sid": None, "status": "opted_out"}

        # Check rate limit
        if self._is_rate_limited(patient):
            logger.info(
                "SMS skipped — rate limited",
                extra={"patient_id": patient.id},
            )
            return {"sid": None, "status": "rate_limited"}

        backend = get_sms_backend()
        result = backend.send_sms(to=str(phone), body=body)

        # Record outbound message
        from apps.messages_app.models import Message

        Message.objects.create(
            patient=patient,
            channel="sms",
            direction="outbound",
            content=body,
            external_id=result.get("sid", ""),
        )

        logger.info(
            "SMS sent",
            extra={
                "patient_id": patient.id,
                "sid": result.get("sid"),
            },
        )

        return result

    def handle_inbound_sms(self, from_number, body, twilio_sid=""):
        """Process an inbound SMS message.

        Args:
            from_number: Sender phone number
            body: Message text
            twilio_sid: Twilio message SID for idempotency

        Returns:
            Dict with 'response' text or None if no response needed
        """
        from apps.accounts.models import User
        from apps.messages_app.models import Message

        # Idempotency check (unique constraint on external_id backs this up)
        if twilio_sid and Message.objects.filter(external_id=twilio_sid).exists():
            logger.info("Duplicate SMS ignored (SID already processed)", extra={"sid": twilio_sid})
            return None

        # Look up patient by phone number
        try:
            user = User.objects.get(phone_number=from_number)
        except User.DoesNotExist:
            logger.info(
                "Inbound SMS from unknown number",
                extra={"from": from_number},
            )
            return None

        if not hasattr(user, "patient_profile"):
            logger.info("Inbound SMS from non-patient user", extra={"user_id": user.id})
            return None

        patient = user.patient_profile

        body_stripped = body.strip()
        body_lower = body_stripped.lower()

        # Handle STOP/START keywords
        try:
            if body_lower in STOP_KEYWORDS:
                self._handle_opt_out(patient)
                Message.objects.create(
                    patient=patient,
                    channel="sms",
                    direction="inbound",
                    content=body_stripped,
                    external_id=twilio_sid,
                )
                return {"response": "You have been unsubscribed. Reply START to re-subscribe."}

            if body_lower in START_KEYWORDS:
                self._handle_opt_in(patient)
                Message.objects.create(
                    patient=patient,
                    channel="sms",
                    direction="inbound",
                    content=body_stripped,
                    external_id=twilio_sid,
                )
                return {"response": "You have been re-subscribed to messages."}
        except IntegrityError:
            logger.info("Duplicate SMS caught by constraint", extra={"sid": twilio_sid})
            return None

        # Process through AI workflow
        from apps.agents.services import process_patient_message

        result = process_patient_message(patient, body_stripped, channel="sms")

        # Send response SMS
        try:
            self.send_sms(patient, result["response_text"])
        except Exception:
            logger.exception("Failed to send SMS response", extra={"patient_id": patient.id})

        return {"response": result["response_text"]}

    def _is_opted_out(self, patient):
        """Check if patient has opted out of SMS."""
        from apps.notifications.models import NotificationPreference

        try:
            pref = NotificationPreference.objects.get(
                patient=patient,
                channel="sms",
                notification_type="update",
            )
            return not pref.enabled
        except NotificationPreference.DoesNotExist:
            return False  # No preference = opted in by default

    def _handle_opt_out(self, patient):
        """Disable SMS for all notification types."""
        from apps.notifications.models import NotificationPreference

        for ntype in ["escalation", "reminder", "alert", "update"]:
            NotificationPreference.objects.update_or_create(
                patient=patient,
                channel="sms",
                notification_type=ntype,
                defaults={"enabled": False},
            )
        logger.info("Patient opted out of SMS", extra={"patient_id": patient.id})

    def _handle_opt_in(self, patient):
        """Re-enable SMS for all notification types."""
        from apps.notifications.models import NotificationPreference

        NotificationPreference.objects.filter(
            patient=patient,
            channel="sms",
        ).update(enabled=True)
        logger.info("Patient opted back into SMS", extra={"patient_id": patient.id})

    def _is_rate_limited(self, patient):
        """Check if patient has exceeded SMS rate limit."""
        from apps.messages_app.models import Message

        limit = getattr(settings, "SMS_RATE_LIMIT_PER_HOUR", 10)
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)

        count = Message.objects.filter(
            patient=patient,
            channel="sms",
            direction="outbound",
            created_at__gte=one_hour_ago,
        ).count()

        return count >= limit
