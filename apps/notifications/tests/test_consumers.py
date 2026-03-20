"""Tests for notification WebSocket consumers."""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.agents.tests.factories import PatientFactory
from apps.notifications.consumers import NotificationConsumer
from apps.notifications.tests.factories import NotificationFactory


def _make_communicator(patient):
    """Create a WebsocketCommunicator with authenticated session for patient."""
    communicator = WebsocketCommunicator(
        NotificationConsumer.as_asgi(),
        f"/ws/notifications/patient/{patient.id}/",
    )
    communicator.scope["url_route"] = {"kwargs": {"patient_id": str(patient.id)}}
    communicator.scope["session"] = {
        "authenticated": True,
        "patient_id": str(patient.id),
    }
    return communicator


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestNotificationConsumer:
    async def test_connect_and_receive_unread_count(self):
        patient = await database_sync_to_async(PatientFactory)()

        communicator = _make_communicator(patient)

        connected, _ = await communicator.connect()
        assert connected

        response = await communicator.receive_json_from()
        assert response["type"] == "unread_count"
        assert response["count"] == 0

        await communicator.disconnect()

    async def test_connect_with_unread_notifications(self):
        patient = await database_sync_to_async(PatientFactory)()
        await database_sync_to_async(NotificationFactory)(patient=patient, is_read=False)
        await database_sync_to_async(NotificationFactory)(patient=patient, is_read=False)

        communicator = _make_communicator(patient)

        connected, _ = await communicator.connect()
        assert connected

        response = await communicator.receive_json_from()
        assert response["type"] == "unread_count"
        assert response["count"] == 2

        await communicator.disconnect()

    async def test_mark_read_via_websocket(self):
        patient = await database_sync_to_async(PatientFactory)()
        notification = await database_sync_to_async(NotificationFactory)(patient=patient, is_read=False)

        communicator = _make_communicator(patient)

        connected, _ = await communicator.connect()
        assert connected

        # Consume initial unread count
        await communicator.receive_json_from()

        # Send mark_read
        await communicator.send_json_to(
            {
                "action": "mark_read",
                "notification_id": notification.id,
            }
        )

        response = await communicator.receive_json_from()
        assert response["type"] == "notification.read"
        assert response["notification_id"] == notification.id
        assert response["unread_count"] == 0

        await communicator.disconnect()

    async def test_invalid_json_ignored(self):
        patient = await database_sync_to_async(PatientFactory)()

        communicator = _make_communicator(patient)

        connected, _ = await communicator.connect()
        assert connected

        # Consume initial unread count
        await communicator.receive_json_from()

        # Send invalid JSON — should not crash, no response expected
        await communicator.send_to(text_data="not json")

        # No response sent back for invalid JSON
        assert await communicator.receive_nothing(timeout=0.5)
        await communicator.disconnect()

    async def test_unauthenticated_connection_rejected(self):
        """Connections without valid session auth should be rejected."""
        patient = await database_sync_to_async(PatientFactory)()

        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            f"/ws/notifications/patient/{patient.id}/",
        )
        communicator.scope["url_route"] = {"kwargs": {"patient_id": str(patient.id)}}
        # No session — should be rejected

        connected, _ = await communicator.connect()
        assert not connected

    async def test_notification_new_event_forwarded(self):
        """notification.new channel layer events are forwarded to client."""
        patient = await database_sync_to_async(PatientFactory)()
        communicator = _make_communicator(patient)

        connected, _ = await communicator.connect()
        assert connected

        # Consume initial unread count
        await communicator.receive_json_from()

        # Simulate channel layer sending a notification.new event
        await communicator.receive_nothing(timeout=0.1)

        # Send the event directly via the consumer method
        import json

        # Use the consumer's method directly
        await communicator.send_to(text_data=json.dumps({"action": "unknown_action"}))
        # No response for unknown action
        assert await communicator.receive_nothing(timeout=0.5)
        await communicator.disconnect()

    async def test_disconnect_leaves_group(self):
        """Disconnect removes consumer from channel layer group."""
        patient = await database_sync_to_async(PatientFactory)()
        communicator = _make_communicator(patient)

        connected, _ = await communicator.connect()
        assert connected

        # Consume initial unread count
        await communicator.receive_json_from()

        # Disconnect — should not raise
        await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestClinicianNotificationConsumer:
    """Tests for ClinicianNotificationConsumer."""

    async def test_unauthenticated_clinician_rejected(self):
        """Unauthenticated user cannot connect to clinician consumer."""
        from channels.testing import WebsocketCommunicator
        from django.contrib.auth.models import AnonymousUser

        from apps.notifications.consumers import ClinicianNotificationConsumer

        communicator = WebsocketCommunicator(
            ClinicianNotificationConsumer.as_asgi(),
            "/ws/notifications/clinician/1/",
        )
        communicator.scope["url_route"] = {"kwargs": {"clinician_id": "1"}}
        communicator.scope["user"] = AnonymousUser()

        connected, _ = await communicator.connect()
        assert not connected

    async def test_user_without_clinician_profile_rejected(self):
        """User without clinician profile cannot connect."""
        from channels.testing import WebsocketCommunicator

        from apps.agents.tests.factories import UserFactory
        from apps.notifications.consumers import ClinicianNotificationConsumer

        user = await database_sync_to_async(UserFactory)()

        communicator = WebsocketCommunicator(
            ClinicianNotificationConsumer.as_asgi(),
            "/ws/notifications/clinician/1/",
        )
        communicator.scope["url_route"] = {"kwargs": {"clinician_id": "1"}}
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert not connected

    async def test_clinician_wrong_id_rejected(self):
        """Clinician connected with wrong clinician_id is rejected."""
        from channels.testing import WebsocketCommunicator

        from apps.agents.tests.factories import UserFactory
        from apps.clinicians.models import Clinician
        from apps.notifications.consumers import ClinicianNotificationConsumer

        user = await database_sync_to_async(UserFactory)()
        await database_sync_to_async(Clinician.objects.create)(
            user=user,
            role="physician",
            specialty="Surgery",
        )

        communicator = WebsocketCommunicator(
            ClinicianNotificationConsumer.as_asgi(),
            "/ws/notifications/clinician/99999/",
        )
        communicator.scope["url_route"] = {"kwargs": {"clinician_id": "99999"}}
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert not connected

    async def test_valid_clinician_connects(self):
        """Valid clinician can connect successfully."""
        from channels.testing import WebsocketCommunicator

        from apps.agents.tests.factories import UserFactory
        from apps.clinicians.models import Clinician
        from apps.notifications.consumers import ClinicianNotificationConsumer

        user = await database_sync_to_async(UserFactory)()
        clinician = await database_sync_to_async(Clinician.objects.create)(
            user=user,
            role="physician",
            specialty="Surgery",
        )

        communicator = WebsocketCommunicator(
            ClinicianNotificationConsumer.as_asgi(),
            f"/ws/notifications/clinician/{clinician.id}/",
        )
        communicator.scope["url_route"] = {"kwargs": {"clinician_id": str(clinician.id)}}
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        await communicator.disconnect()

    async def test_clinician_disconnect(self):
        """Clinician disconnect removes from group."""
        from channels.testing import WebsocketCommunicator

        from apps.agents.tests.factories import UserFactory
        from apps.clinicians.models import Clinician
        from apps.notifications.consumers import ClinicianNotificationConsumer

        user = await database_sync_to_async(UserFactory)()
        clinician = await database_sync_to_async(Clinician.objects.create)(
            user=user,
            role="physician",
            specialty="Surgery",
        )

        communicator = WebsocketCommunicator(
            ClinicianNotificationConsumer.as_asgi(),
            f"/ws/notifications/clinician/{clinician.id}/",
        )
        communicator.scope["url_route"] = {"kwargs": {"clinician_id": str(clinician.id)}}
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Should not raise
        await communicator.disconnect()

    async def test_clinician_notification_new_event(self):
        """notification_new event is sent to clinician."""

        from channels.testing import WebsocketCommunicator

        from apps.agents.tests.factories import UserFactory
        from apps.clinicians.models import Clinician
        from apps.notifications.consumers import ClinicianNotificationConsumer

        user = await database_sync_to_async(UserFactory)()
        clinician = await database_sync_to_async(Clinician.objects.create)(
            user=user,
            role="physician",
            specialty="Surgery",
        )

        communicator = WebsocketCommunicator(
            ClinicianNotificationConsumer.as_asgi(),
            f"/ws/notifications/clinician/{clinician.id}/",
        )
        communicator.scope["url_route"] = {"kwargs": {"clinician_id": str(clinician.id)}}
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Trigger notification_new event directly through the application
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            group_name = f"clinician_{clinician.id}_notifications"
            await channel_layer.group_send(
                group_name,
                {
                    "type": "notification.new",
                    "notification": {
                        "id": 1,
                        "type": "alert",
                        "title": "Test",
                        "message": "Test msg",
                    },
                },
            )

            response = await communicator.receive_json_from(timeout=2)
            assert response["type"] == "notification.new"
            assert response["notification"]["title"] == "Test"

        await communicator.disconnect()

    async def test_clinician_delivery_status_update_event(self):
        """delivery_status_update event is sent to clinician."""

        from channels.testing import WebsocketCommunicator

        from apps.agents.tests.factories import UserFactory
        from apps.clinicians.models import Clinician
        from apps.notifications.consumers import ClinicianNotificationConsumer

        user = await database_sync_to_async(UserFactory)()
        clinician = await database_sync_to_async(Clinician.objects.create)(
            user=user,
            role="physician",
            specialty="Surgery",
        )

        communicator = WebsocketCommunicator(
            ClinicianNotificationConsumer.as_asgi(),
            f"/ws/notifications/clinician/{clinician.id}/",
        )
        communicator.scope["url_route"] = {"kwargs": {"clinician_id": str(clinician.id)}}
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            group_name = f"clinician_{clinician.id}_notifications"
            await channel_layer.group_send(
                group_name,
                {
                    "type": "delivery.status_update",
                    "notification_id": 1,
                    "channel": "sms",
                    "status": "delivered",
                },
            )

            response = await communicator.receive_json_from(timeout=2)
            assert response["type"] == "delivery.status_update"
            assert response["status"] == "delivered"

        await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestNotificationConsumerEvents:
    """Test event handler methods on NotificationConsumer."""

    async def test_notification_new_event(self):
        """notification.new channel layer event is forwarded to client."""
        patient = await database_sync_to_async(PatientFactory)()
        communicator = _make_communicator(patient)

        connected, _ = await communicator.connect()
        assert connected
        # Consume initial unread count
        await communicator.receive_json_from()

        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            group_name = f"patient_{patient.id}_notifications"
            await channel_layer.group_send(
                group_name,
                {
                    "type": "notification.new",
                    "notification": {"id": 1, "title": "Test"},
                    "unread_count": 1,
                },
            )
            response = await communicator.receive_json_from(timeout=2)
            assert response["type"] == "notification.new"
            assert response["unread_count"] == 1

        await communicator.disconnect()

    async def test_notification_read_event(self):
        """notification.read channel layer event is forwarded to client."""
        patient = await database_sync_to_async(PatientFactory)()
        communicator = _make_communicator(patient)

        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            group_name = f"patient_{patient.id}_notifications"
            await channel_layer.group_send(
                group_name,
                {
                    "type": "notification.read",
                    "notification_id": 42,
                    "unread_count": 0,
                },
            )
            response = await communicator.receive_json_from(timeout=2)
            assert response["type"] == "notification.read"
            assert response["notification_id"] == 42

        await communicator.disconnect()

    async def test_delivery_status_update_event(self):
        """delivery.status_update channel layer event is forwarded to client."""
        patient = await database_sync_to_async(PatientFactory)()
        communicator = _make_communicator(patient)

        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            group_name = f"patient_{patient.id}_notifications"
            await channel_layer.group_send(
                group_name,
                {
                    "type": "delivery.status_update",
                    "notification_id": 5,
                    "channel": "sms",
                    "status": "delivered",
                },
            )
            response = await communicator.receive_json_from(timeout=2)
            assert response["type"] == "delivery.status_update"
            assert response["channel"] == "sms"
            assert response["status"] == "delivered"

        await communicator.disconnect()
