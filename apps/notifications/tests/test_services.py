"""Tests for notification service."""

import pytest

from apps.agents.tests.factories import PatientFactory
from apps.notifications.backends import LocMemBackend
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.notifications.tests.factories import (
    NotificationDeliveryFactory,
    NotificationFactory,
    NotificationPreferenceFactory,
)


@pytest.mark.django_db
class TestCreateNotification:
    def test_creates_notification_with_deliveries(self):
        patient = PatientFactory()
        n = NotificationService.create_notification(
            patient=patient,
            notification_type="alert",
            severity="warning",
            title="Reminder",
            message="Time for your check-in",
            channels=["in_app", "sms"],
        )

        assert n.id is not None
        assert n.patient == patient
        assert n.title == "Reminder"
        assert n.deliveries.count() == 2
        channels = set(n.deliveries.values_list("channel", flat=True))
        assert channels == {"in_app", "sms"}

    def test_defaults_to_patient_preferences(self):
        patient = PatientFactory()
        NotificationPreferenceFactory(
            patient=patient,
            channel="sms",
            notification_type="alert",
            enabled=True,
        )
        NotificationPreferenceFactory(
            patient=patient,
            channel="email",
            notification_type="alert",
            enabled=True,
        )

        n = NotificationService.create_notification(
            patient=patient,
            notification_type="alert",
            severity="info",
            title="Test",
            message="Test",
        )

        channels = set(n.deliveries.values_list("channel", flat=True))
        assert channels == {"sms", "email"}

    def test_defaults_to_in_app_when_no_preferences(self):
        patient = PatientFactory()
        n = NotificationService.create_notification(
            patient=patient,
            notification_type="alert",
            severity="info",
            title="Test",
            message="Test",
        )

        channels = list(n.deliveries.values_list("channel", flat=True))
        assert channels == ["in_app"]

    def test_clinician_notification(self):
        from apps.agents.tests.factories import UserFactory
        from apps.clinicians.models import Clinician

        user = UserFactory()
        clinician = Clinician.objects.create(user=user, role="physician", specialty="Surgery")

        n = NotificationService.create_notification(
            clinician=clinician,
            notification_type="escalation",
            severity="critical",
            title="Escalation",
            message="Patient needs attention",
            channels=["in_app"],
        )

        assert n.clinician == clinician
        assert n.patient is None


@pytest.mark.django_db
class TestDeliverNotification:
    def setup_method(self):
        LocMemBackend.reset()

    def test_delivers_via_backend(self, settings):
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
        }
        from apps.notifications.backends import _import_backend_class

        _import_backend_class.cache_clear()

        n = NotificationFactory()
        NotificationDeliveryFactory(notification=n, channel="in_app")

        results = NotificationService.deliver_notification(n.id)

        assert results["in_app"] is True
        assert len(LocMemBackend.outbox) == 1

    def test_skips_disabled_channel(self):
        patient = PatientFactory()
        NotificationPreferenceFactory(
            patient=patient,
            channel="sms",
            notification_type="alert",
            enabled=False,
        )

        n = NotificationFactory(patient=patient, notification_type="alert")
        NotificationDeliveryFactory(notification=n, channel="sms")

        results = NotificationService.deliver_notification(n.id)

        assert results["sms"] is False
        d = n.deliveries.first()
        assert d.status == "failed"
        assert "disabled" in d.error_message

    def test_defers_during_quiet_hours(self):
        patient = PatientFactory()
        # Set quiet hours that cover "now"
        import datetime

        from django.utils import timezone

        now = timezone.localtime().time()
        start = (datetime.datetime.combine(datetime.date.today(), now) - datetime.timedelta(hours=1)).time()
        end = (datetime.datetime.combine(datetime.date.today(), now) + datetime.timedelta(hours=1)).time()

        NotificationPreferenceFactory(
            patient=patient,
            channel="in_app",
            notification_type="alert",
            quiet_hours_start=start,
            quiet_hours_end=end,
        )

        n = NotificationFactory(patient=patient, notification_type="alert")
        NotificationDeliveryFactory(notification=n, channel="in_app")

        results = NotificationService.deliver_notification(n.id)

        assert results["in_app"] is None  # deferred
        d = n.deliveries.first()
        assert d.status == "pending"  # still pending

    def test_nonexistent_notification(self):
        results = NotificationService.deliver_notification(99999)
        assert results == {}


@pytest.mark.django_db
class TestMarkRead:
    def test_marks_read(self):
        n = NotificationFactory(is_read=False)
        NotificationService.mark_read(n.id)

        n.refresh_from_db()
        assert n.is_read is True
        assert n.read_at is not None


@pytest.mark.django_db
class TestGetUnread:
    def test_get_unread_for_patient(self):
        patient = PatientFactory()
        NotificationFactory(patient=patient, is_read=False)
        NotificationFactory(patient=patient, is_read=True)
        NotificationFactory(patient=patient, is_read=False)

        unread = NotificationService.get_unread_for_patient(patient.id)
        assert unread.count() == 2

    def test_get_unread_for_clinician(self):
        from apps.agents.tests.factories import UserFactory
        from apps.clinicians.models import Clinician

        user = UserFactory()
        clinician = Clinician.objects.create(user=user, role="physician", specialty="Surgery")

        NotificationFactory(clinician=clinician, is_read=False)
        NotificationFactory(clinician=clinician, is_read=True)

        unread = NotificationService.get_unread_for_clinician(clinician.id)
        assert unread.count() == 1


@pytest.mark.django_db
class TestCreateEscalationNotification:
    def test_creates_patient_notification(self):
        from apps.agents.tests.factories import EscalationFactory

        escalation = EscalationFactory(severity="critical")
        NotificationService.create_escalation_notification(escalation)

        notifications = Notification.objects.filter(
            patient=escalation.patient,
            notification_type="escalation",
        )
        assert notifications.count() == 1
        assert notifications.first().title == "Your care team has been notified"
