"""Tests for notification models."""

import pytest
from django.db import IntegrityError

from apps.notifications.models import (
    Notification,
    NotificationDelivery,
)
from apps.notifications.tests.factories import (
    NotificationDeliveryFactory,
    NotificationFactory,
    NotificationPreferenceFactory,
)


@pytest.mark.django_db
class TestNotification:
    def test_create(self):
        n = NotificationFactory()
        assert n.id is not None
        assert n.is_read is False
        assert n.read_at is None

    def test_str(self):
        n = NotificationFactory(severity="critical", title="High fever")
        assert str(n) == "critical - High fever"

    def test_ordering_newest_first(self):
        n1 = NotificationFactory(title="First")
        n2 = NotificationFactory(title="Second")
        result = list(Notification.objects.all())
        assert result[0].id == n2.id
        assert result[1].id == n1.id

    def test_patient_nullable(self):
        n = NotificationFactory(patient=None)
        assert n.patient is None

    def test_clinician_nullable(self):
        n = NotificationFactory(clinician=None)
        assert n.clinician is None


@pytest.mark.django_db
class TestNotificationDelivery:
    def test_create_defaults(self):
        d = NotificationDeliveryFactory()
        assert d.status == "pending"
        assert d.retry_count == 0
        assert d.external_id == ""
        assert d.error_message == ""
        assert d.delivered_at is None

    def test_str(self):
        d = NotificationDeliveryFactory(channel="sms", status="sent")
        assert "sms" in str(d)
        assert "sent" in str(d)

    def test_cascade_delete(self):
        d = NotificationDeliveryFactory()
        notification_id = d.notification.id
        d.notification.delete()
        assert not NotificationDelivery.objects.filter(notification_id=notification_id).exists()

    def test_multiple_deliveries_per_notification(self):
        n = NotificationFactory()
        NotificationDeliveryFactory(notification=n, channel="in_app")
        NotificationDeliveryFactory(notification=n, channel="sms")
        assert n.deliveries.count() == 2

    def test_status_choices(self):
        for status in ["pending", "sent", "delivered", "failed"]:
            d = NotificationDeliveryFactory(status=status)
            assert d.status == status


@pytest.mark.django_db
class TestNotificationPreference:
    def test_create(self):
        p = NotificationPreferenceFactory()
        assert p.enabled is True
        assert p.quiet_hours_start is None

    def test_str(self):
        p = NotificationPreferenceFactory(enabled=False)
        assert "disabled" in str(p)

    def test_unique_constraint(self):
        p = NotificationPreferenceFactory(channel="sms", notification_type="escalation")
        with pytest.raises(IntegrityError):
            NotificationPreferenceFactory(
                patient=p.patient,
                channel="sms",
                notification_type="escalation",
            )

    def test_different_types_same_channel_allowed(self):
        p = NotificationPreferenceFactory(channel="sms", notification_type="escalation")
        p2 = NotificationPreferenceFactory(
            patient=p.patient,
            channel="sms",
            notification_type="reminder",
        )
        assert p2.id is not None

    def test_quiet_hours(self):
        from datetime import time

        p = NotificationPreferenceFactory(
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(7, 0),
        )
        assert p.quiet_hours_start == time(22, 0)
        assert p.quiet_hours_end == time(7, 0)
