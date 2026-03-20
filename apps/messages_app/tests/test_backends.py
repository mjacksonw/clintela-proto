"""Tests for SMS backends."""

import io
import sys
from unittest.mock import MagicMock, patch

from apps.messages_app.backends import (
    BaseSMSBackend,
    ConsoleSMSBackend,
    LocMemSMSBackend,
    TwilioSMSBackend,
    get_sms_backend,
)


class TestConsoleSMSBackend:
    def test_prints_to_stdout(self):
        backend = ConsoleSMSBackend()
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            result = backend.send_sms("+15551234567", "Hello from test")
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        assert "SMS" in output
        assert "+15551234567" in output
        assert "Hello from test" in output
        assert result["sid"].startswith("CONSOLE_")
        assert result["status"] == "sent"


class TestLocMemSMSBackend:
    def setup_method(self):
        LocMemSMSBackend.reset()

    def test_stores_in_outbox(self):
        backend = LocMemSMSBackend()
        result = backend.send_sms("+15551234567", "Test message")

        assert len(LocMemSMSBackend.outbox) == 1
        assert LocMemSMSBackend.outbox[0]["to"] == "+15551234567"
        assert LocMemSMSBackend.outbox[0]["body"] == "Test message"
        assert result["sid"].startswith("LOCMEM_")

    def test_reset_clears_outbox(self):
        LocMemSMSBackend().send_sms("+15551234567", "Test")
        assert len(LocMemSMSBackend.outbox) == 1
        LocMemSMSBackend.reset()
        assert len(LocMemSMSBackend.outbox) == 0


class TestBaseSMSBackend:
    def test_send_sms_raises_not_implemented(self):
        import pytest

        backend = BaseSMSBackend()
        with pytest.raises(NotImplementedError):
            backend.send_sms("+15551234567", "Hello")


class TestTwilioSMSBackend:
    def setup_method(self):
        # Reset singleton
        TwilioSMSBackend._instance = None

    def test_singleton_pattern(self):
        b1 = TwilioSMSBackend()
        b2 = TwilioSMSBackend()
        assert b1 is b2

    def test_reads_settings(self, settings):
        TwilioSMSBackend._instance = None
        settings.TWILIO_ACCOUNT_SID = "ACtest123"
        settings.TWILIO_AUTH_TOKEN = "auth_token_xyz"
        settings.TWILIO_PHONE_NUMBER = "+15550001111"

        backend = TwilioSMSBackend()
        assert backend.account_sid == "ACtest123"
        assert backend.auth_token == "auth_token_xyz"
        assert backend.default_from == "+15550001111"

    def test_client_property_creates_twilio_client(self, settings):
        TwilioSMSBackend._instance = None
        settings.TWILIO_ACCOUNT_SID = "ACtest"
        settings.TWILIO_AUTH_TOKEN = "token"

        backend = TwilioSMSBackend()
        backend._client = None

        mock_twilio_client = MagicMock()
        with patch("twilio.rest.Client", return_value=mock_twilio_client):
            client = backend.client
            assert client is mock_twilio_client

    def test_send_sms_raises_when_no_from_number(self, settings):
        import pytest

        TwilioSMSBackend._instance = None
        settings.TWILIO_PHONE_NUMBER = None

        backend = TwilioSMSBackend()
        backend.default_from = None

        mock_client = MagicMock()
        with (
            patch.object(type(backend), "client", new_callable=lambda: property(lambda self: mock_client)),
            pytest.raises(ValueError, match="No from_number"),
        ):
            backend.send_sms("+15551234567", "Hello", from_number=None)

    def test_send_sms_uses_twilio_client(self, settings):
        TwilioSMSBackend._instance = None
        settings.TWILIO_PHONE_NUMBER = "+15550001111"

        backend = TwilioSMSBackend()

        mock_message = MagicMock()
        mock_message.sid = "SM_test_sid"
        mock_message.status = "queued"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch.object(type(backend), "client", new_callable=lambda: property(lambda self: mock_client)):
            result = backend.send_sms("+15559999999", "Test message")

        assert result == {"sid": "SM_test_sid", "status": "queued"}
        mock_client.messages.create.assert_called_once()

    def test_get_status_callback_url_with_base_url(self, settings):
        TwilioSMSBackend._instance = None
        settings.TWILIO_STATUS_CALLBACK_BASE_URL = "https://example.com"

        backend = TwilioSMSBackend()
        url = backend._get_status_callback_url()
        assert url == "https://example.com/sms/status/"

    def test_get_status_callback_url_without_base_url(self, settings):
        TwilioSMSBackend._instance = None
        settings.TWILIO_STATUS_CALLBACK_BASE_URL = None

        backend = TwilioSMSBackend()
        url = backend._get_status_callback_url()
        assert url is None

    def test_send_sms_with_explicit_from_number(self, settings):
        TwilioSMSBackend._instance = None
        settings.TWILIO_PHONE_NUMBER = "+15550001111"
        settings.TWILIO_STATUS_CALLBACK_BASE_URL = None

        backend = TwilioSMSBackend()

        mock_message = MagicMock()
        mock_message.sid = "SM_explicit"
        mock_message.status = "sent"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch.object(type(backend), "client", new_callable=lambda: property(lambda self: mock_client)):
            backend.send_sms("+15559999999", "Hello", from_number="+15550002222")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["from_"] == "+15550002222"


class TestGetSmsBackend:
    def test_returns_configured_backend(self, settings):
        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        from apps.messages_app.backends import _import_sms_backend_class

        _import_sms_backend_class.cache_clear()

        backend = get_sms_backend()
        assert isinstance(backend, LocMemSMSBackend)
