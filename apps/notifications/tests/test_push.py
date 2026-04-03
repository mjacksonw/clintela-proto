"""Tests for push notification infrastructure.

Covers:
  - DeviceToken model CRUD and lifecycle
  - PushBackend delivery (mocked FCM)
  - Push delivery Celery task with retry
  - Notification routing hierarchy (WS > Push > SMS)
  - Push fan-out (one delivery per device)
  - WS suppression (active WS skips push)
  - SMS daily cap
  - Caregiver push relay
"""

import sys
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError
from django.utils import timezone

# firebase_admin is not installed in the test env; provide a stub so that
# ``from firebase_admin import messaging`` inside PushBackend.send() resolves.
_firebase_stub = MagicMock()
sys.modules.setdefault("firebase_admin", _firebase_stub)
sys.modules.setdefault("firebase_admin.messaging", _firebase_stub.messaging)

from apps.agents.tests.factories import (  # noqa: E402
    CaregiverFactory,
    CaregiverRelationshipFactory,
    PatientFactory,
    UserFactory,
)
from apps.notifications.backends import LocMemBackend, _import_backend_class  # noqa: E402
from apps.notifications.models import DeviceToken, Notification, NotificationDelivery  # noqa: E402
from apps.notifications.services import NotificationService  # noqa: E402
from apps.notifications.tests.factories import (  # noqa: E402
    DeviceTokenFactory,
    NotificationDeliveryFactory,
    NotificationFactory,
)

# ──────────────────────────────────────────────────────────────────────
# DeviceToken Model CRUD
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDeviceTokenModel:
    def test_create_device_token(self):
        patient = PatientFactory()
        token = DeviceToken.objects.create(
            patient=patient,
            platform="ios",
            token="test_fcm_token_001",
            device_name="iPhone 15",
        )
        assert token.is_active is True
        assert token.deactivated_at is None
        assert str(token) == f"{patient} - ios (active)"

    def test_token_unique_constraint(self):
        DeviceTokenFactory(token="unique_token_123")
        with pytest.raises(IntegrityError):
            DeviceTokenFactory(token="unique_token_123")

    def test_deactivate_token(self):
        token = DeviceTokenFactory()
        token.is_active = False
        token.deactivated_at = timezone.now()
        token.save()
        token.refresh_from_db()
        assert token.is_active is False
        assert token.deactivated_at is not None
        assert "inactive" in str(token)

    def test_patient_multiple_tokens(self):
        patient = PatientFactory()
        DeviceTokenFactory(patient=patient, token="tok_a")
        DeviceTokenFactory(patient=patient, token="tok_b", platform="android")
        active = DeviceToken.objects.filter(patient=patient, is_active=True)
        assert active.count() == 2

    def test_patient_fk_nullable_for_caregiver(self):
        """Caregiver device tokens use user FK instead of patient FK."""
        user = UserFactory()
        token = DeviceToken.objects.create(
            user=user,
            platform="android",
            token="caregiver_token_001",
            device_name="Pixel 8",
        )
        assert token.patient is None
        assert token.user == user

    def test_index_on_patient_active(self):
        """Verify the composite index exists for efficient fan-out queries."""
        meta = DeviceToken._meta
        index_names = [idx.name for idx in meta.indexes]
        assert "idx_device_patient_active" in index_names


# ──────────────────────────────────────────────────────────────────────
# PushBackend
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPushBackend:
    def setup_method(self):
        LocMemBackend.reset()

    def test_push_backend_no_device_fails(self):
        """Push delivery with no device FK fails gracefully."""
        from apps.notifications.backends import PushBackend

        n = NotificationFactory()
        d = NotificationDeliveryFactory(notification=n, channel="push")
        # d.device is None

        backend = PushBackend()
        result = backend.send(n, d)

        assert result is False
        d.refresh_from_db()
        assert d.status == "failed"
        assert "No device token" in d.error_message

    def test_push_backend_inactive_device_bounces(self):
        """Push to an inactive device token marks delivery as bounced."""
        from apps.notifications.backends import PushBackend

        device = DeviceTokenFactory(is_active=False)
        n = NotificationFactory(patient=device.patient)
        d = NotificationDeliveryFactory(notification=n, channel="push", device=device)

        backend = PushBackend()
        result = backend.send(n, d)

        assert result is False
        d.refresh_from_db()
        assert d.status == "bounced"

    @patch("firebase_admin.messaging")
    def test_push_backend_success(self, mock_messaging):
        """Successful push via FCM sets status=sent and external_id."""
        from apps.notifications.backends import PushBackend

        mock_messaging.send.return_value = "projects/test/messages/12345"

        device = DeviceTokenFactory()
        n = NotificationFactory(patient=device.patient)
        d = NotificationDeliveryFactory(notification=n, channel="push", device=device)

        backend = PushBackend()
        result = backend.send(n, d)

        assert result is True
        d.refresh_from_db()
        assert d.status == "sent"
        assert d.external_id == "projects/test/messages/12345"

    @patch("firebase_admin.messaging")
    def test_push_backend_gone_deactivates_token(self, mock_messaging):
        """APNs 410/gone deactivates the token and marks delivery as bounced."""
        from apps.notifications.backends import PushBackend

        mock_messaging.send.side_effect = Exception("Requested entity was not found. (unregistered)")

        device = DeviceTokenFactory()
        n = NotificationFactory(patient=device.patient)
        d = NotificationDeliveryFactory(notification=n, channel="push", device=device)

        backend = PushBackend()
        result = backend.send(n, d)

        assert result is False
        d.refresh_from_db()
        assert d.status == "bounced"
        assert "Token gone" in d.error_message
        device.refresh_from_db()
        assert device.is_active is False
        assert device.deactivated_at is not None

    @patch("firebase_admin.messaging")
    def test_push_backend_transient_failure(self, mock_messaging):
        """Non-gone FCM error marks delivery as failed with retry."""
        from apps.notifications.backends import PushBackend

        mock_messaging.send.side_effect = Exception("Internal server error")

        device = DeviceTokenFactory()
        n = NotificationFactory(patient=device.patient)
        d = NotificationDeliveryFactory(notification=n, channel="push", device=device)

        backend = PushBackend()
        result = backend.send(n, d)

        assert result is False
        d.refresh_from_db()
        assert d.status == "failed"
        assert d.retry_count == 1
        # Token should still be active (transient, not gone)
        device.refresh_from_db()
        assert device.is_active is True

    @patch("firebase_admin.messaging")
    def test_push_backend_phi_safe_preview(self, mock_messaging):
        """Push notification body is generic (no PHI on lock screen)."""
        from apps.notifications.backends import PushBackend

        mock_messaging.send.return_value = "msg_id"

        device = DeviceTokenFactory()
        n = NotificationFactory(
            patient=device.patient,
            notification_type="reminder",
            title="Take Lisinopril 10mg",  # PHI
            message="Your blood pressure medication is due",  # PHI
        )
        d = NotificationDeliveryFactory(notification=n, channel="push", device=device)

        backend = PushBackend()
        backend.send(n, d)

        # Verify the Notification constructor was called with generic (PHI-safe) content
        mock_messaging.Notification.assert_called_once_with(
            title="Clintela",
            body="Time for a check-in",  # Generic, not the PHI title/message
        )


# ──────────────────────────────────────────────────────────────────────
# Notification Routing Hierarchy
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestNotificationRouting:
    def setup_method(self):
        LocMemBackend.reset()
        _import_backend_class.cache_clear()

    def test_ws_active_suppresses_push_and_sms(self, settings):
        """When WS is active (<60s), push and SMS are suppressed."""
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
            "push": "apps.notifications.backends.LocMemBackend",
            "sms": "apps.notifications.backends.LocMemBackend",
        }
        settings.ENABLE_MOBILE_PUSH = True
        _import_backend_class.cache_clear()

        patient = PatientFactory()
        # Simulate active WS session
        patient.user.last_active_at = timezone.now() - timedelta(seconds=10)
        patient.user.save()

        DeviceTokenFactory(patient=patient)

        n = NotificationService.create_notification(
            patient=patient,
            notification_type="reminder",
            title="Check-in",
            message="Time to check in",
            channels=["in_app", "push", "sms"],
        )

        deliveries = NotificationDelivery.objects.filter(notification=n)
        channels = {d.channel for d in deliveries}
        assert "in_app" in channels
        assert "push" not in channels
        assert "sms" not in channels

    def test_push_tokens_replace_sms(self, settings):
        """When push tokens exist but WS is inactive, push replaces SMS."""
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
            "push": "apps.notifications.backends.LocMemBackend",
            "sms": "apps.notifications.backends.LocMemBackend",
        }
        settings.ENABLE_MOBILE_PUSH = True
        _import_backend_class.cache_clear()

        patient = PatientFactory()
        # No WS activity
        patient.user.last_active_at = None
        patient.user.save()

        DeviceTokenFactory(patient=patient)

        n = NotificationService.create_notification(
            patient=patient,
            notification_type="reminder",
            title="Check-in",
            message="Time to check in",
            channels=["in_app", "sms"],
        )

        deliveries = NotificationDelivery.objects.filter(notification=n)
        channels = {d.channel for d in deliveries}
        assert "in_app" in channels
        assert "push" in channels
        assert "sms" not in channels

    def test_no_push_tokens_falls_back_to_sms(self, settings):
        """When no push tokens exist, SMS is kept as fallback."""
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
            "push": "apps.notifications.backends.LocMemBackend",
            "sms": "apps.notifications.backends.LocMemBackend",
        }
        settings.ENABLE_MOBILE_PUSH = True
        _import_backend_class.cache_clear()

        patient = PatientFactory()
        patient.user.last_active_at = None
        patient.user.save()

        # No device tokens created

        n = NotificationService.create_notification(
            patient=patient,
            notification_type="reminder",
            title="Check-in",
            message="Time to check in",
            channels=["in_app", "sms"],
        )

        deliveries = NotificationDelivery.objects.filter(notification=n)
        channels = {d.channel for d in deliveries}
        assert "in_app" in channels
        assert "sms" in channels
        assert "push" not in channels

    def test_escalation_bypasses_routing(self, settings):
        """Escalation notifications go through all channels regardless."""
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
            "push": "apps.notifications.backends.LocMemBackend",
            "sms": "apps.notifications.backends.LocMemBackend",
        }
        settings.ENABLE_MOBILE_PUSH = True
        _import_backend_class.cache_clear()

        patient = PatientFactory()
        # Even with active WS, escalations go everywhere
        patient.user.last_active_at = timezone.now() - timedelta(seconds=5)
        patient.user.save()

        DeviceTokenFactory(patient=patient)

        n = NotificationService.create_notification(
            patient=patient,
            notification_type="escalation",
            title="Care team contact",
            message="A nurse will follow up",
            channels=["in_app", "push", "sms"],
        )

        deliveries = NotificationDelivery.objects.filter(notification=n)
        channels = {d.channel for d in deliveries}
        assert "in_app" in channels
        assert "push" in channels
        assert "sms" in channels

    def test_push_fan_out_per_device(self, settings):
        """Push creates one NotificationDelivery per active device token."""
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
            "push": "apps.notifications.backends.LocMemBackend",
        }
        settings.ENABLE_MOBILE_PUSH = True
        _import_backend_class.cache_clear()

        patient = PatientFactory()
        patient.user.last_active_at = None
        patient.user.save()

        d1 = DeviceTokenFactory(patient=patient, token="dev_1")
        d2 = DeviceTokenFactory(patient=patient, token="dev_2", platform="android")
        # Inactive device should not get a delivery
        DeviceTokenFactory(patient=patient, token="dev_3_inactive", is_active=False)

        n = NotificationService.create_notification(
            patient=patient,
            notification_type="reminder",
            title="Check-in",
            message="Time",
            channels=["push"],
        )

        push_deliveries = NotificationDelivery.objects.filter(notification=n, channel="push")
        assert push_deliveries.count() == 2
        device_ids = {d.device_id for d in push_deliveries}
        assert d1.id in device_ids
        assert d2.id in device_ids

    def test_push_disabled_by_feature_flag(self, settings):
        """When ENABLE_MOBILE_PUSH=False, routing is skipped."""
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
            "push": "apps.notifications.backends.LocMemBackend",
            "sms": "apps.notifications.backends.LocMemBackend",
        }
        settings.ENABLE_MOBILE_PUSH = False
        _import_backend_class.cache_clear()

        patient = PatientFactory()
        DeviceTokenFactory(patient=patient)

        n = NotificationService.create_notification(
            patient=patient,
            notification_type="reminder",
            title="Test",
            message="Test",
            channels=["in_app", "sms"],
        )

        deliveries = NotificationDelivery.objects.filter(notification=n)
        channels = {d.channel for d in deliveries}
        # No routing applied — original channels preserved
        assert "in_app" in channels
        assert "sms" in channels


# ──────────────────────────────────────────────────────────────────────
# SMS Daily Cap
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSMSCap:
    def setup_method(self):
        LocMemBackend.reset()
        _import_backend_class.cache_clear()

    def test_sms_cap_blocks_after_5_per_day(self, settings):
        """Automated SMS is capped at 5 per patient per day."""
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
            "sms": "apps.notifications.backends.LocMemBackend",
        }
        _import_backend_class.cache_clear()

        patient = PatientFactory()

        # Send 5 successful SMS deliveries
        for _i in range(5):
            n = NotificationFactory(patient=patient, notification_type="reminder")
            NotificationDelivery.objects.create(
                notification=n,
                channel="sms",
                status="sent",
            )

        # 6th SMS should be deferred (cap hit)
        n6 = NotificationFactory(patient=patient, notification_type="reminder")
        NotificationDelivery.objects.create(
            notification=n6,
            channel="sms",
            status="pending",
        )

        results = NotificationService.deliver_notification(n6.id)
        assert results.get("sms") is None  # Deferred

    def test_sms_cap_bypassed_for_escalations(self, settings):
        """Care team messages (escalations) bypass the SMS daily cap."""
        settings.NOTIFICATION_BACKENDS = {
            "in_app": "apps.notifications.backends.LocMemBackend",
            "sms": "apps.notifications.backends.LocMemBackend",
        }
        _import_backend_class.cache_clear()

        patient = PatientFactory()

        # Send 5 SMS
        for _i in range(5):
            n = NotificationFactory(patient=patient, notification_type="reminder")
            NotificationDelivery.objects.create(notification=n, channel="sms", status="sent")

        # Escalation should bypass cap
        n_esc = NotificationFactory(patient=patient, notification_type="escalation")
        NotificationDelivery.objects.create(
            notification=n_esc,
            channel="sms",
            status="pending",
        )

        results = NotificationService.deliver_notification(n_esc.id)
        assert results.get("sms") is True


# ──────────────────────────────────────────────────────────────────────
# Caregiver Push Relay
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCaregiverPushRelay:
    def test_relay_creates_caregiver_notification(self):
        """Escalation notification relays to caregiver with active tokens."""
        from apps.notifications.caregiver_push import relay_to_caregivers

        patient = PatientFactory()
        caregiver = CaregiverFactory()
        CaregiverRelationshipFactory(caregiver=caregiver, patient=patient)

        # Give caregiver a device token
        DeviceToken.objects.create(
            user=caregiver.user,
            platform="ios",
            token="caregiver_token_001",
            is_active=True,
        )

        notification = NotificationFactory(
            patient=patient,
            notification_type="escalation",
            severity="warning",
            title="Escalation triggered",
            message="Care team notified",
        )

        count = relay_to_caregivers(notification)
        assert count == 1

        # Caregiver notification should exist with generic (PHI-safe) message
        caregiver_notifs = Notification.objects.filter(
            patient=patient,
        ).exclude(id=notification.id)
        assert caregiver_notifs.count() == 1
        cn = caregiver_notifs.first()
        assert patient.user.first_name in cn.title
        assert "care team" in cn.message.lower()

    def test_relay_skips_non_relayable_types(self):
        """Reminder notifications are not relayed to caregivers."""
        from apps.notifications.caregiver_push import relay_to_caregivers

        notification = NotificationFactory(notification_type="reminder")
        count = relay_to_caregivers(notification)
        assert count == 0

    def test_relay_skips_caregivers_without_tokens(self):
        """Caregivers without device tokens are skipped."""
        from apps.notifications.caregiver_push import relay_to_caregivers

        patient = PatientFactory()
        caregiver = CaregiverFactory()
        CaregiverRelationshipFactory(caregiver=caregiver, patient=patient)
        # No device token for caregiver

        notification = NotificationFactory(
            patient=patient,
            notification_type="escalation",
        )

        count = relay_to_caregivers(notification)
        assert count == 0

    def test_relay_skips_inactive_relationships(self):
        """Inactive caregiver relationships are skipped."""
        from apps.notifications.caregiver_push import relay_to_caregivers

        patient = PatientFactory()
        caregiver = CaregiverFactory()
        CaregiverRelationshipFactory(caregiver=caregiver, patient=patient, is_active=False)

        DeviceToken.objects.create(
            user=caregiver.user,
            platform="ios",
            token="inactive_rel_token",
            is_active=True,
        )

        notification = NotificationFactory(
            patient=patient,
            notification_type="escalation",
        )

        count = relay_to_caregivers(notification)
        assert count == 0


# ──────────────────────────────────────────────────────────────────────
# Push Delivery Task
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPushDeliveryTask:
    def setup_method(self):
        LocMemBackend.reset()
        _import_backend_class.cache_clear()

    def test_deliver_push_task_success(self, settings):
        """Push delivery task delivers and returns True."""
        settings.NOTIFICATION_BACKENDS = {
            "push": "apps.notifications.backends.LocMemBackend",
        }
        _import_backend_class.cache_clear()

        device = DeviceTokenFactory()
        n = NotificationFactory(patient=device.patient)
        d = NotificationDeliveryFactory(notification=n, channel="push", device=device)

        from apps.notifications.tasks import deliver_push_notification_task

        result = deliver_push_notification_task(d.id)
        assert result is True
        d.refresh_from_db()
        assert d.status == "delivered"  # LocMemBackend marks as delivered

    def test_deliver_push_task_skips_non_pending(self, settings):
        """Task does nothing for already-processed deliveries."""
        settings.NOTIFICATION_BACKENDS = {
            "push": "apps.notifications.backends.LocMemBackend",
        }
        _import_backend_class.cache_clear()

        device = DeviceTokenFactory()
        n = NotificationFactory(patient=device.patient)
        d = NotificationDeliveryFactory(notification=n, channel="push", device=device, status="sent")

        from apps.notifications.tasks import deliver_push_notification_task

        result = deliver_push_notification_task(d.id)
        assert result is None  # Skipped
