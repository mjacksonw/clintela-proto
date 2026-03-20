"""SMS delivery backends.

Backend hierarchy:
    BaseSMSBackend.send_sms(to, body, from_number) -> dict
    ├── TwilioSMSBackend     — real Twilio API (production)
    ├── ConsoleSMSBackend    — prints to runserver stdout
    └── LocMemSMSBackend     — stores in .outbox list (tests)

Configuration via SMS_BACKEND setting (dotted class path).
"""

import importlib
import logging
import sys
from functools import cache

from django.conf import settings

logger = logging.getLogger(__name__)


class BaseSMSBackend:
    """Abstract base for SMS backends."""

    def send_sms(self, to, body, from_number=None):
        """Send an SMS message.

        Args:
            to: Recipient phone number (E.164 format)
            body: Message text
            from_number: Sender phone number (defaults to TWILIO_PHONE_NUMBER)

        Returns:
            Dict with at least 'sid' and 'status' keys
        """
        raise NotImplementedError


class TwilioSMSBackend(BaseSMSBackend):
    """Real Twilio SMS backend for production."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
        self.auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
        self.default_from = getattr(settings, "TWILIO_PHONE_NUMBER", None)
        self._client = None
        self._initialized = True

    @property
    def client(self):
        if self._client is None:
            from twilio.rest import Client

            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    def send_sms(self, to, body, from_number=None):
        from_number = from_number or self.default_from
        if not from_number:
            raise ValueError("No from_number and TWILIO_PHONE_NUMBER not configured")

        message = self.client.messages.create(
            to=to,
            from_=from_number,
            body=body,
            status_callback=self._get_status_callback_url(),
        )

        logger.info(
            "Twilio SMS sent",
            extra={"sid": message.sid, "to": to, "status": message.status},
        )

        return {"sid": message.sid, "status": message.status}

    def _get_status_callback_url(self):
        """Get the status callback URL for Twilio delivery reports."""
        base_url = getattr(settings, "TWILIO_STATUS_CALLBACK_BASE_URL", None)
        if base_url:
            return f"{base_url.rstrip('/')}/sms/status/"
        return None


class ConsoleSMSBackend(BaseSMSBackend):
    """Prints SMS to stdout — for development use."""

    _message_counter = 0

    def send_sms(self, to, body, from_number=None):
        from_number = from_number or getattr(settings, "TWILIO_PHONE_NUMBER", "+15555555555")
        ConsoleSMSBackend._message_counter += 1
        sid = f"CONSOLE_{ConsoleSMSBackend._message_counter:06d}"

        output = (
            f"\n{'═' * 40} SMS {'═' * 5}\n"
            f"  To:   {to}\n"
            f"  From: {from_number}\n"
            f"  Body: {body}\n"
            f"{'═' * 50}\n"
        )
        sys.stdout.write(output)
        sys.stdout.flush()

        return {"sid": sid, "status": "sent"}


class LocMemSMSBackend(BaseSMSBackend):
    """In-memory backend for testing."""

    outbox = []

    def send_sms(self, to, body, from_number=None):
        from_number = from_number or getattr(settings, "TWILIO_PHONE_NUMBER", "+15555555555")
        sid = f"LOCMEM_{len(LocMemSMSBackend.outbox) + 1:06d}"

        LocMemSMSBackend.outbox.append(
            {
                "sid": sid,
                "to": to,
                "from": from_number,
                "body": body,
                "status": "sent",
            }
        )

        return {"sid": sid, "status": "sent"}

    @classmethod
    def reset(cls):
        cls.outbox.clear()


@cache
def _import_sms_backend_class(dotted_path):
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_sms_backend():
    """Get the configured SMS backend instance.

    Reads from settings.SMS_BACKEND.
    """
    dotted_path = getattr(settings, "SMS_BACKEND", "apps.messages_app.backends.ConsoleSMSBackend")
    backend_class = _import_sms_backend_class(dotted_path)
    return backend_class()
