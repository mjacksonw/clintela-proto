"""Tests for notification delivery backends."""

import io
import sys

import pytest

from apps.notifications.backends import (
    ConsoleBackend,
    InAppBackend,
    LocMemBackend,
    get_notification_backend,
)
from apps.notifications.tests.factories import (
    NotificationDeliveryFactory,
    NotificationFactory,
)


@pytest.mark.django_db
class TestInAppBackend:
    def test_marks_delivered(self):
        n = NotificationFactory()
        d = NotificationDeliveryFactory(notification=n, channel="in_app")
        backend = InAppBackend()

        result = backend.send(n, d)

        assert result is True
        d.refresh_from_db()
        assert d.status == "delivered"
        assert d.delivered_at is not None


@pytest.mark.django_db
class TestConsoleBackend:
    def test_prints_to_stdout(self):
        n = NotificationFactory(
            title="Test Alert",
            message="Check your vitals",
            severity="warning",
        )
        d = NotificationDeliveryFactory(notification=n, channel="sms")
        backend = ConsoleBackend()

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            result = backend.send(n, d)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        assert "NOTIFICATION" in output
        assert "Test Alert" in output
        assert "Check your vitals" in output
        assert "warning" in output
        assert result is True

    def test_marks_delivered(self):
        n = NotificationFactory()
        d = NotificationDeliveryFactory(notification=n)
        backend = ConsoleBackend()

        # Suppress stdout
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            backend.send(n, d)
        finally:
            sys.stdout = old_stdout

        d.refresh_from_db()
        assert d.status == "delivered"
        assert d.delivered_at is not None


@pytest.mark.django_db
class TestLocMemBackend:
    def setup_method(self):
        LocMemBackend.reset()

    def test_stores_in_outbox(self):
        n = NotificationFactory(title="Hello")
        d = NotificationDeliveryFactory(notification=n)
        backend = LocMemBackend()

        result = backend.send(n, d)

        assert result is True
        assert len(LocMemBackend.outbox) == 1
        assert LocMemBackend.outbox[0]["title"] == "Hello"

    def test_reset_clears_outbox(self):
        n = NotificationFactory()
        d = NotificationDeliveryFactory(notification=n)
        LocMemBackend().send(n, d)

        assert len(LocMemBackend.outbox) == 1
        LocMemBackend.reset()
        assert len(LocMemBackend.outbox) == 0

    def test_marks_delivered(self):
        n = NotificationFactory()
        d = NotificationDeliveryFactory(notification=n)
        LocMemBackend().send(n, d)

        d.refresh_from_db()
        assert d.status == "delivered"


@pytest.mark.django_db
class TestSMSBackend:
    """Tests for SMSBackend."""

    def setup_method(self):
        from apps.messages_app.backends import LocMemSMSBackend

        LocMemSMSBackend.reset()

    def test_fails_when_no_patient(self):
        from apps.notifications.backends import SMSBackend

        n = NotificationFactory(patient=None, clinician=None)
        n.patient = None  # explicitly set
        n.save()
        NotificationDeliveryFactory(notification=n, channel="sms")
        backend = SMSBackend()

        # reload from db to get null patient
        from apps.notifications.models import Notification

        n_fresh = Notification.objects.select_related("patient").get(id=n.id)
        d_fresh = n_fresh.deliveries.first()

        result = backend.send(n_fresh, d_fresh)

        assert result is False
        d_fresh.refresh_from_db()
        assert d_fresh.status == "failed"
        assert "No patient" in d_fresh.error_message

    def test_fails_when_patient_has_no_phone(self, settings):
        from apps.agents.tests.factories import PatientFactory
        from apps.notifications.backends import SMSBackend

        patient = PatientFactory()
        patient.user.phone_number = ""
        patient.user.save()

        n = NotificationFactory(patient=patient)
        d = NotificationDeliveryFactory(notification=n, channel="sms")
        backend = SMSBackend()

        result = backend.send(n, d)

        assert result is False
        d.refresh_from_db()
        assert d.status == "failed"
        assert "phone number" in d.error_message

    def test_sends_sms_successfully(self, settings):
        from apps.agents.tests.factories import PatientFactory
        from apps.messages_app.backends import LocMemSMSBackend, _import_sms_backend_class
        from apps.notifications.backends import SMSBackend

        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        settings.ENABLE_SMS = True
        _import_sms_backend_class.cache_clear()

        patient = PatientFactory()
        n = NotificationFactory(patient=patient, title="Alert", message="Check vitals")
        d = NotificationDeliveryFactory(notification=n, channel="sms")
        backend = SMSBackend()

        result = backend.send(n, d)

        assert result is True
        d.refresh_from_db()
        assert d.status == "sent"
        assert len(LocMemSMSBackend.outbox) == 1

    def test_sms_failure_marks_delivery_failed(self, settings):
        from unittest.mock import patch

        from apps.agents.tests.factories import PatientFactory
        from apps.notifications.backends import SMSBackend

        settings.ENABLE_SMS = True
        patient = PatientFactory()
        n = NotificationFactory(patient=patient)
        d = NotificationDeliveryFactory(notification=n, channel="sms")
        backend = SMSBackend()

        with patch("apps.messages_app.services.SMSService.send_sms", side_effect=Exception("Twilio error")):
            result = backend.send(n, d)

        assert result is False
        d.refresh_from_db()
        assert d.status == "failed"
        assert d.retry_count == 1


@pytest.mark.django_db
class TestEmailBackend:
    """Tests for EmailBackend."""

    def test_fails_when_no_recipient(self):
        from apps.notifications.backends import EmailBackend

        n = NotificationFactory(patient=None)
        n.patient = None
        n.clinician = None
        n.save()

        from apps.notifications.models import Notification

        n_fresh = Notification.objects.select_related("patient", "clinician").get(id=n.id)
        d = NotificationDeliveryFactory(notification=n_fresh, channel="email")
        backend = EmailBackend()

        result = backend.send(n_fresh, d)

        assert result is False
        d.refresh_from_db()
        assert d.status == "failed"
        assert "No recipient" in d.error_message

    def test_fails_when_recipient_has_no_email(self):
        from apps.agents.tests.factories import PatientFactory
        from apps.notifications.backends import EmailBackend

        patient = PatientFactory()
        patient.user.email = ""
        patient.user.save()

        n = NotificationFactory(patient=patient)
        d = NotificationDeliveryFactory(notification=n, channel="email")
        backend = EmailBackend()

        result = backend.send(n, d)

        assert result is False
        d.refresh_from_db()
        assert d.status == "failed"
        assert "no email address" in d.error_message

    def test_sends_email_successfully(self):
        from django.core import mail

        from apps.agents.tests.factories import PatientFactory
        from apps.notifications.backends import EmailBackend

        patient = PatientFactory()
        patient.user.email = "patient@example.com"
        patient.user.save()

        n = NotificationFactory(patient=patient, title="Test Email", message="Your check-in is due")
        d = NotificationDeliveryFactory(notification=n, channel="email")
        backend = EmailBackend()

        result = backend.send(n, d)

        assert result is True
        d.refresh_from_db()
        assert d.status == "sent"
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Test Email"
        assert "patient@example.com" in mail.outbox[0].to

    def test_email_failure_marks_delivery_failed(self):
        from unittest.mock import patch

        from apps.agents.tests.factories import PatientFactory
        from apps.notifications.backends import EmailBackend

        patient = PatientFactory()
        patient.user.email = "patient@example.com"
        patient.user.save()

        n = NotificationFactory(patient=patient)
        d = NotificationDeliveryFactory(notification=n, channel="email")
        backend = EmailBackend()

        with patch("django.core.mail.send_mail", side_effect=Exception("SMTP error")):
            result = backend.send(n, d)

        assert result is False
        d.refresh_from_db()
        assert d.status == "failed"
        assert d.retry_count == 1


@pytest.mark.django_db
class TestGetNotificationBackend:
    def test_returns_configured_backend(self, settings):
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
        }
        # Clear the lru_cache
        from apps.notifications.backends import _import_backend_class

        _import_backend_class.cache_clear()

        backend = get_notification_backend("in_app")
        assert isinstance(backend, LocMemBackend)

    def test_falls_back_to_console(self, settings):
        settings.NOTIFICATION_BACKENDS = {}
        backend = get_notification_backend("unknown_channel")
        assert isinstance(backend, ConsoleBackend)
