"""Tests for SMS service."""

import pytest

from apps.agents.tests.factories import PatientFactory
from apps.messages_app.backends import LocMemSMSBackend
from apps.messages_app.models import Message
from apps.messages_app.services import SMSService
from apps.notifications.models import NotificationPreference


@pytest.mark.django_db
class TestSendSms:
    def setup_method(self):
        LocMemSMSBackend.reset()

    def test_sends_sms(self, settings):
        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        settings.ENABLE_SMS = True
        from apps.messages_app.backends import _import_sms_backend_class

        _import_sms_backend_class.cache_clear()

        patient = PatientFactory()
        sms = SMSService()
        result = sms.send_sms(patient, "Hello patient!")

        assert result["status"] == "sent"
        assert len(LocMemSMSBackend.outbox) == 1
        assert LocMemSMSBackend.outbox[0]["body"] == "Hello patient!"

    def test_records_message(self, settings):
        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        settings.ENABLE_SMS = True
        from apps.messages_app.backends import _import_sms_backend_class

        _import_sms_backend_class.cache_clear()

        patient = PatientFactory()
        SMSService().send_sms(patient, "Test body")

        msg = Message.objects.filter(patient=patient, channel="sms", direction="outbound").first()
        assert msg is not None
        assert msg.content == "Test body"

    def test_skips_opted_out_patient(self, settings):
        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        settings.ENABLE_SMS = True

        patient = PatientFactory()
        NotificationPreference.objects.create(
            patient=patient,
            channel="sms",
            notification_type="update",
            enabled=False,
        )

        result = SMSService().send_sms(patient, "Hello")
        assert result["status"] == "opted_out"
        assert len(LocMemSMSBackend.outbox) == 0

    def test_raises_on_no_phone(self, settings):
        settings.ENABLE_SMS = True
        patient = PatientFactory()
        patient.user.phone_number = ""
        patient.user.save()

        with pytest.raises(ValueError, match="no phone"):
            SMSService().send_sms(patient, "Hello")


@pytest.mark.django_db
class TestHandleInboundSms:
    def setup_method(self):
        LocMemSMSBackend.reset()

    def test_idempotency(self, settings):
        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        from apps.messages_app.backends import _import_sms_backend_class

        _import_sms_backend_class.cache_clear()

        patient = PatientFactory()
        # Pre-create a message with this SID
        Message.objects.create(
            patient=patient,
            channel="sms",
            direction="inbound",
            content="First time",
            external_id="SM_DUPLICATE",
        )

        result = SMSService().handle_inbound_sms(
            from_number=str(patient.user.phone_number),
            body="Duplicate",
            twilio_sid="SM_DUPLICATE",
        )

        assert result is None  # Skipped

    def test_unknown_number(self):
        result = SMSService().handle_inbound_sms(
            from_number="+19999999999",
            body="Hello",
        )
        assert result is None

    def test_stop_keyword_opts_out(self, settings):
        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"

        patient = PatientFactory()
        result = SMSService().handle_inbound_sms(
            from_number=str(patient.user.phone_number),
            body="STOP",
        )

        assert "unsubscribed" in result["response"].lower()
        # Check preferences were created
        prefs = NotificationPreference.objects.filter(patient=patient, channel="sms", enabled=False)
        assert prefs.count() == 4  # All 4 notification types

    def test_start_keyword_opts_in(self, settings):
        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"

        patient = PatientFactory()
        # First opt out
        for ntype in ["escalation", "reminder", "alert", "update"]:
            NotificationPreference.objects.create(
                patient=patient,
                channel="sms",
                notification_type=ntype,
                enabled=False,
            )

        result = SMSService().handle_inbound_sms(
            from_number=str(patient.user.phone_number),
            body="START",
        )

        assert "re-subscribed" in result["response"].lower()
        prefs = NotificationPreference.objects.filter(patient=patient, channel="sms", enabled=True)
        assert prefs.count() == 4

    def test_non_patient_user_returns_none(self):
        """SMS from a user without a patient_profile is ignored."""
        import uuid

        from apps.accounts.models import User

        # Use a unique phone number to avoid xdist collisions
        unique_phone = f"+1555{uuid.uuid4().int % 10000000:07d}"
        User.objects.create_user(
            username=f"staffonly_{uuid.uuid4().hex[:8]}",
            phone_number=unique_phone,
        )

        result = SMSService().handle_inbound_sms(
            from_number=unique_phone,
            body="Hello",
        )

        assert result is None

    def test_inbound_sms_processes_through_ai(self, settings):
        """Normal inbound SMS is processed via AI and response sent."""
        from unittest.mock import patch

        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        settings.ENABLE_SMS = True
        from apps.messages_app.backends import _import_sms_backend_class

        _import_sms_backend_class.cache_clear()
        LocMemSMSBackend.reset()

        patient = PatientFactory()

        with patch("apps.agents.services.process_patient_message") as mock_process:
            mock_process.return_value = {
                "response_text": "I understand. Please rest and stay hydrated.",
                "agent_message": None,
                "escalate": False,
            }
            result = SMSService().handle_inbound_sms(
                from_number=str(patient.user.phone_number),
                body="My knee hurts",
            )

        assert result is not None
        assert "response" in result
        mock_process.assert_called_once_with(patient, "My knee hurts", channel="sms")

    def test_inbound_sms_response_send_failure_is_swallowed(self, settings):
        """Failed response SMS send does not raise."""
        from unittest.mock import patch

        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        settings.ENABLE_SMS = True
        from apps.messages_app.backends import _import_sms_backend_class

        _import_sms_backend_class.cache_clear()

        patient = PatientFactory()

        with patch("apps.agents.services.process_patient_message") as mock_process:
            mock_process.return_value = {
                "response_text": "Here is my response.",
                "agent_message": None,
                "escalate": False,
            }
            with patch.object(SMSService, "send_sms", side_effect=Exception("SMS error")):
                result = SMSService().handle_inbound_sms(
                    from_number=str(patient.user.phone_number),
                    body="Hello",
                )

        # Should still return the result despite send failure
        assert result is not None


@pytest.mark.django_db
class TestSendSmsRateLimit:
    def setup_method(self):
        LocMemSMSBackend.reset()

    def test_rate_limited_returns_rate_limited_status(self, settings):
        """Patient exceeding rate limit gets 'rate_limited' status."""
        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        settings.ENABLE_SMS = True
        settings.SMS_RATE_LIMIT_PER_HOUR = 2
        from apps.messages_app.backends import _import_sms_backend_class

        _import_sms_backend_class.cache_clear()

        patient = PatientFactory()

        # Create outbound messages to hit rate limit
        from apps.messages_app.models import Message

        Message.objects.create(patient=patient, channel="sms", direction="outbound", content="msg1")
        Message.objects.create(patient=patient, channel="sms", direction="outbound", content="msg2")

        result = SMSService().send_sms(patient, "Third message")
        assert result["status"] == "rate_limited"

    def test_sms_disabled_raises_in_non_debug(self, settings):
        """SMS disabled raises when not in DEBUG."""
        settings.ENABLE_SMS = False
        settings.DEBUG = False

        patient = PatientFactory()
        with pytest.raises(ValueError, match="SMS is disabled"):
            SMSService().send_sms(patient, "Hello")
