"""Tests for SMS backends."""

import io
import sys

from apps.messages_app.backends import (
    ConsoleSMSBackend,
    LocMemSMSBackend,
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


class TestGetSmsBackend:
    def test_returns_configured_backend(self, settings):
        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        from apps.messages_app.backends import _import_sms_backend_class

        _import_sms_backend_class.cache_clear()

        backend = get_sms_backend()
        assert isinstance(backend, LocMemSMSBackend)
