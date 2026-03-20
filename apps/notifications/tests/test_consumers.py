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
