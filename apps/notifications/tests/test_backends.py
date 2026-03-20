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
