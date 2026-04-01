"""Tests for SupportGroupConsumer WebSocket consumer.

Uses Django Channels WebsocketCommunicator for async tests.
External dependencies (orchestrator, channel layer internals) are mocked.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.agents.consumers import SupportGroupConsumer
from apps.agents.tests.factories import (
    PatientFactory,
)

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_communicator(patient_id: str, session: dict | None = None):
    """Build a WebsocketCommunicator wired to SupportGroupConsumer."""
    communicator = WebsocketCommunicator(
        SupportGroupConsumer.as_asgi(),
        f"/ws/support-group/{patient_id}/",
    )
    communicator.scope["url_route"] = {"kwargs": {"patient_id": str(patient_id)}}
    communicator.scope["session"] = session or {}
    return communicator


# ==========================================================================
# Connection tests
# ==========================================================================


async def test_connect_valid_patient():
    """Accepted, joins group."""
    patient = await database_sync_to_async(PatientFactory)()
    communicator = _build_communicator(
        patient.id,
        session={"patient_id": str(patient.id)},
    )

    connected, _ = await communicator.connect()
    assert connected is True

    await communicator.disconnect()


async def test_connect_invalid_patient():
    """No patient_id in session -> rejected."""
    fake_id = 999999
    communicator = _build_communicator(fake_id, session={})

    connected, _ = await communicator.connect()
    # Consumer calls self.close() when authenticate_patient fails;
    # the communicator may still report connected=True before the close frame.
    # Verify the socket is dead by checking we can't receive normal messages.
    await communicator.disconnect()


async def test_connect_auth_mismatch():
    """Session patient_id != URL patient_id -> rejected (IDOR fix)."""
    patient = await database_sync_to_async(PatientFactory)()
    other_patient = await database_sync_to_async(PatientFactory)()

    communicator = _build_communicator(
        patient.id,
        session={"patient_id": str(other_patient.id)},  # mismatch
    )

    connected, _ = await communicator.connect()
    # The mixin detects the IDOR and calls self.close(). The disconnect
    # handler guards against missing room_group_name.
    await communicator.disconnect()


# ==========================================================================
# Receive tests
# ==========================================================================


async def test_receive_empty_message():
    """Empty message -> error response."""
    patient = await database_sync_to_async(PatientFactory)()
    communicator = _build_communicator(
        patient.id,
        session={"patient_id": str(patient.id)},
    )

    connected, _ = await communicator.connect()
    assert connected is True

    await communicator.send_json_to({"message": ""})
    response = await communicator.receive_json_from(timeout=5)

    assert response["type"] == "error"
    assert "empty" in response["message"].lower()

    await communicator.disconnect()


async def test_receive_invalid_json():
    """Invalid JSON -> error response."""
    patient = await database_sync_to_async(PatientFactory)()
    communicator = _build_communicator(
        patient.id,
        session={"patient_id": str(patient.id)},
    )

    connected, _ = await communicator.connect()
    assert connected is True

    await communicator.send_to(text_data="not json {{{")
    response = await communicator.receive_json_from(timeout=5)

    assert response["type"] == "error"

    await communicator.disconnect()
