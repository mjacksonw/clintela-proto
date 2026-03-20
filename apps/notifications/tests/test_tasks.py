"""Tests for notification Celery tasks."""

import pytest

from apps.notifications.backends import LocMemBackend
from apps.notifications.tasks import deliver_notification_task, send_scheduled_reminders
from apps.notifications.tests.factories import (
    NotificationDeliveryFactory,
    NotificationFactory,
)


@pytest.mark.django_db
class TestDeliverNotificationTask:
    def setup_method(self):
        LocMemBackend.reset()

    def test_delivers_notification(self, settings):
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
        }
        from apps.notifications.backends import _import_backend_class

        _import_backend_class.cache_clear()

        n = NotificationFactory()
        NotificationDeliveryFactory(notification=n, channel="in_app")

        result = deliver_notification_task(n.id)

        assert result["in_app"] is True
        assert len(LocMemBackend.outbox) == 1


@pytest.mark.django_db
class TestSendScheduledReminders:
    def setup_method(self):
        LocMemBackend.reset()

    def test_processes_pending_reminders(self, settings):
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
        }
        from apps.notifications.backends import _import_backend_class

        _import_backend_class.cache_clear()

        n = NotificationFactory(notification_type="reminder")
        NotificationDeliveryFactory(notification=n, channel="in_app")

        result = send_scheduled_reminders()

        assert result["processed"] == 1

    def test_skips_non_reminder_types(self, settings):
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
        }

        n = NotificationFactory(notification_type="alert")
        NotificationDeliveryFactory(notification=n, channel="in_app")

        result = send_scheduled_reminders()

        assert result["processed"] == 0

    def test_returns_zero_when_nothing_pending(self):
        result = send_scheduled_reminders()
        assert result["processed"] == 0
