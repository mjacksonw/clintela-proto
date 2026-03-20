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
