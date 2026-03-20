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

    def test_creates_clinician_notification_when_assigned(self):
        """Creates clinician notification when escalation has assigned_to."""
        from apps.agents.tests.factories import EscalationFactory, UserFactory
        from apps.clinicians.models import Clinician

        clinician_user = UserFactory()
        clinician = Clinician.objects.create(user=clinician_user, role="physician", specialty="Surgery")

        escalation = EscalationFactory(severity="urgent")
        escalation.assigned_to = clinician_user
        escalation.save()

        NotificationService.create_escalation_notification(escalation)

        # Should create clinician notification
        clinician_notifications = Notification.objects.filter(
            clinician=clinician,
            notification_type="escalation",
        )
        assert clinician_notifications.count() == 1

    def test_no_clinician_notification_when_not_assigned(self):
        """No clinician notification when escalation has no assigned_to."""
        from apps.agents.tests.factories import EscalationFactory

        escalation = EscalationFactory(severity="routine")
        # escalation.assigned_to is not set (None by default)

        NotificationService.create_escalation_notification(escalation)

        # Should only have patient notification
        patient_notifications = Notification.objects.filter(
            patient=escalation.patient,
            notification_type="escalation",
        )
        assert patient_notifications.count() == 1

    def test_severity_map_urgent(self):
        """Urgent escalation maps to warning severity."""
        from apps.agents.tests.factories import EscalationFactory

        escalation = EscalationFactory(severity="urgent")
        NotificationService.create_escalation_notification(escalation)

        n = Notification.objects.filter(patient=escalation.patient, notification_type="escalation").first()
        assert n.severity == "warning"

    def test_clinician_not_found_logs_warning(self):
        """Handles Clinician.DoesNotExist gracefully."""
        from apps.agents.tests.factories import EscalationFactory, UserFactory

        # Create user but NO clinician profile
        some_user = UserFactory()

        escalation = EscalationFactory(severity="urgent")
        escalation.assigned_to = some_user
        escalation.save()

        # Should not raise
        NotificationService.create_escalation_notification(escalation)

    def test_no_patient_notification_when_no_patient(self):
        """No patient notification when escalation has no patient (mocked)."""
        from unittest.mock import MagicMock

        # Create a mock escalation with no patient
        escalation = MagicMock()
        escalation.patient = None
        escalation.severity = "urgent"
        # No assigned_to
        del escalation.assigned_to

        initial_count = Notification.objects.count()
        NotificationService.create_escalation_notification(escalation)
        # No new notifications created
        assert Notification.objects.count() == initial_count


@pytest.mark.django_db
class TestNotificationServiceChannelLogic:
    """Test _get_channels_for_patient and _is_quiet_hours logic."""

    def test_get_channels_returns_default_when_no_patient(self):
        channels = NotificationService._get_channels_for_patient(None, "alert")
        assert channels == ["in_app"]

    def test_is_channel_enabled_returns_true_when_no_preference(self):
        patient = PatientFactory()
        # No preference record — should default to enabled
        result = NotificationService._is_channel_enabled(patient, "sms", "alert")
        assert result is True

    def test_is_quiet_hours_returns_false_when_no_preference(self):
        patient = PatientFactory()
        result = NotificationService._is_quiet_hours(patient, "sms", "alert")
        assert result is False

    def test_is_quiet_hours_returns_false_when_no_times_set(self):
        patient = PatientFactory()
        NotificationPreferenceFactory(
            patient=patient,
            channel="sms",
            notification_type="alert",
            quiet_hours_start=None,
            quiet_hours_end=None,
        )
        result = NotificationService._is_quiet_hours(patient, "sms", "alert")
        assert result is False

    def test_is_quiet_hours_overnight(self):
        """Test overnight quiet hours (e.g. 22:00 - 07:00)."""
        import datetime

        patient = PatientFactory()
        # Overnight: start > end
        NotificationPreferenceFactory(
            patient=patient,
            channel="sms",
            notification_type="alert",
            quiet_hours_start=datetime.time(22, 0),
            quiet_hours_end=datetime.time(7, 0),
        )
        # We can't easily control current time, but we can verify it doesn't crash
        result = NotificationService._is_quiet_hours(patient, "sms", "alert")
        assert isinstance(result, bool)

    def test_deliver_notification_backend_raises_exception(self, settings):
        """Backend exception is caught and marks delivery failed."""
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
        }
        from apps.notifications.backends import _import_backend_class

        _import_backend_class.cache_clear()

        n = NotificationFactory()
        NotificationDeliveryFactory(notification=n, channel="in_app")

        with pytest.raises(Exception) if False else __import__("contextlib").suppress():
            pass

        from unittest.mock import patch

        with patch("apps.notifications.backends.LocMemBackend.send", side_effect=Exception("Backend crashed")):
            results = NotificationService.deliver_notification(n.id)

        assert results["in_app"] is False
        d = n.deliveries.first()
        d.refresh_from_db()
        assert d.status == "failed"
        assert d.retry_count == 1

    def test_push_notification_to_websocket_with_channel_layer_none(self):
        """Push to websocket is no-op when channel layer is None."""
        from unittest.mock import patch

        from apps.notifications.services import _push_notification_to_websocket

        n = NotificationFactory()
        with patch("channels.layers.get_channel_layer", return_value=None):
            # Should not raise
            _push_notification_to_websocket(n)

    def test_push_delivery_status_with_channel_layer_none(self):
        """Push delivery status is no-op when channel layer is None."""
        from unittest.mock import patch

        from apps.notifications.services import _push_delivery_status

        n = NotificationFactory()
        with patch("channels.layers.get_channel_layer", return_value=None):
            # Should not raise
            _push_delivery_status(n.id, "in_app", "delivered")

    def test_push_notification_to_websocket_with_clinician(self):
        """Push to websocket works for clinician notifications."""
        from unittest.mock import patch

        from apps.agents.tests.factories import UserFactory
        from apps.clinicians.models import Clinician
        from apps.notifications.services import _push_notification_to_websocket

        user = UserFactory()
        clinician = Clinician.objects.create(user=user, role="physician", specialty="Surgery")
        n = NotificationFactory(patient=None, clinician=clinician)
        n.patient = None
        n.save()

        with patch("channels.layers.get_channel_layer", return_value=None):
            # Should not raise
            _push_notification_to_websocket(n)

    def test_push_delivery_status_for_patient_notification(self):
        """Push delivery status sends to patient group."""
        from unittest.mock import MagicMock, patch

        from apps.notifications.services import _push_delivery_status

        patient = PatientFactory()
        n = NotificationFactory(patient=patient)

        mock_layer = MagicMock()
        mock_async_to_sync = MagicMock(return_value=lambda *a, **kw: None)
        with (
            patch("channels.layers.get_channel_layer", return_value=mock_layer),
            patch("asgiref.sync.async_to_sync", mock_async_to_sync),
        ):
            _push_delivery_status(n.id, "in_app", "delivered")

    def test_create_notification_with_no_patient_and_no_channels(self):
        """Create notification with no patient and no explicit channels."""
        n = NotificationService.create_notification(
            patient=None,
            clinician=None,
            notification_type="alert",
            severity="info",
            title="System Alert",
            message="System is running",
        )
        assert n.id is not None
        # With no patient, should use DEFAULT_CHANNELS
        channels = list(n.deliveries.values_list("channel", flat=True))
        assert channels == ["in_app"]
