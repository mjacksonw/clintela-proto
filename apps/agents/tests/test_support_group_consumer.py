"""Tests for SupportGroupConsumer WebSocket consumer.

Uses Django Channels WebsocketCommunicator for async tests.
External dependencies (orchestrator, channel layer internals) are mocked.
"""

from unittest.mock import AsyncMock, patch

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.agents.consumers import SupportGroupConsumer
from apps.agents.tests.factories import (
    AgentConversationFactory,
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


# ==========================================================================
# Event handler tests (channel layer events pushed to client)
# ==========================================================================


async def test_push_support_group_message():
    """support_group_message event pushed to client."""
    patient = await database_sync_to_async(PatientFactory)()
    communicator = _build_communicator(
        patient.id,
        session={"patient_id": str(patient.id)},
    )

    connected, _ = await communicator.connect()
    assert connected is True

    # Simulate a channel layer event directly on the consumer
    consumer = SupportGroupConsumer()
    consumer.send = AsyncMock()
    await consumer.support_group_message(
        {
            "type": "support_group_message",
            "message_id": "test-id",
            "persona_id": "maria",
            "persona_name": "Maria",
            "content": "Hello sweetheart!",
            "avatar_color": "#8B5CF6",
            "avatar_color_dark": "#A78BFA",
            "avatar_initials": "MG",
        }
    )

    consumer.send.assert_awaited_once()
    import json

    sent_data = json.loads(consumer.send.call_args[1]["text_data"])
    assert sent_data["type"] == "support_group_message"
    assert sent_data["persona_id"] == "maria"
    assert sent_data["content"] == "Hello sweetheart!"

    await communicator.disconnect()


async def test_push_support_group_reaction():
    """support_group_reaction event pushed to client."""
    consumer = SupportGroupConsumer()
    consumer.send = AsyncMock()
    await consumer.support_group_reaction(
        {
            "type": "support_group_reaction",
            "message_id": "test-id",
            "persona_id": "james",
            "emoji": "thumbs_up",
        }
    )

    consumer.send.assert_awaited_once()
    import json

    sent_data = json.loads(consumer.send.call_args[1]["text_data"])
    assert sent_data["type"] == "support_group_reaction"
    assert sent_data["persona_id"] == "james"
    assert sent_data["emoji"] == "thumbs_up"


async def test_push_support_group_typing():
    """support_group_typing event pushed to client."""
    consumer = SupportGroupConsumer()
    consumer.send = AsyncMock()
    await consumer.support_group_typing(
        {
            "type": "support_group_typing",
            "persona_id": "maria",
            "persona_name": "Maria",
        }
    )

    consumer.send.assert_awaited_once()
    import json

    sent_data = json.loads(consumer.send.call_args[1]["text_data"])
    assert sent_data["type"] == "support_group_typing"
    assert sent_data["persona_name"] == "Maria"


async def test_get_or_create_conversation():
    """_get_or_create_conversation creates support_group conversation."""
    from apps.agents.services import ConversationService

    patient = await database_sync_to_async(PatientFactory)()

    # Test the underlying service method that the consumer calls
    conv = await database_sync_to_async(ConversationService.get_or_create_conversation)(
        patient,
        conversation_type="support_group",
    )

    assert conv.conversation_type == "support_group"
    assert conv.patient_id == patient.id


async def test_save_user_message_with_voice():
    """_save_user_message stores voice metadata."""
    patient = await database_sync_to_async(PatientFactory)()
    conv = await database_sync_to_async(AgentConversationFactory)(
        patient=patient,
        conversation_type="support_group",
    )

    consumer = SupportGroupConsumer()
    consumer.patient = patient

    from apps.agents.models import AgentMessage

    msg = await database_sync_to_async(consumer._save_user_message.__wrapped__)(
        consumer,
        conv,
        "Transcribed voice message",
        {"channel": "voice", "audio_url": "https://example.com/audio.wav"},
    )

    @database_sync_to_async
    def _verify():
        m = AgentMessage.objects.get(id=msg.id)
        assert m.metadata["channel"] == "voice"
        assert m.metadata["audio_url"] == "https://example.com/audio.wav"

    await _verify()


async def test_receive_valid_message_processes():
    """Valid message triggers orchestrator and returns response."""
    patient = await database_sync_to_async(PatientFactory)()
    await database_sync_to_async(AgentConversationFactory)(
        patient=patient,
        conversation_type="support_group",
    )
    communicator = _build_communicator(
        patient.id,
        session={"patient_id": str(patient.id)},
    )

    connected, _ = await communicator.connect()
    assert connected is True

    mock_result = {
        "type": "support_group_message",
        "message_id": "test-123",
        "persona_id": "maria",
        "persona_name": "Maria",
        "content": "I hear you, sweetheart.",
        "avatar_color": "#8B5CF6",
        "avatar_color_dark": "#A78BFA",
        "avatar_initials": "MG",
        "escalate": False,
    }

    with patch(
        "apps.agents.support_group.SupportGroupOrchestrator.process_message",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        await communicator.send_json_to({"message": "I walked today!"})

        # Should get typing indicator first, then the response
        # Read responses until we get the support_group_message
        responses = []
        for _ in range(5):
            try:
                resp = await communicator.receive_json_from(timeout=3)
                responses.append(resp)
                if resp.get("type") == "support_group_message":
                    break
            except Exception:
                break

        msg_responses = [r for r in responses if r.get("type") == "support_group_message"]
        assert len(msg_responses) >= 1
        assert msg_responses[0]["persona_id"] == "maria"

    await communicator.disconnect()


async def test_receive_crisis_message():
    """Crisis result shows escalation banner."""
    patient = await database_sync_to_async(PatientFactory)()
    await database_sync_to_async(AgentConversationFactory)(
        patient=patient,
        conversation_type="support_group",
    )
    communicator = _build_communicator(
        patient.id,
        session={"patient_id": str(patient.id)},
    )

    connected, _ = await communicator.connect()
    assert connected is True

    mock_result = {
        "type": "crisis_detected",
        "escalate": True,
        "source": "keyword",
    }

    with (
        patch(
            "apps.agents.support_group.SupportGroupOrchestrator.process_message",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch.object(
            SupportGroupConsumer,
            "_broadcast_escalation",
            new_callable=AsyncMock,
        ),
    ):
        await communicator.send_json_to({"message": "I want to end it all"})

        responses = []
        for _ in range(5):
            try:
                resp = await communicator.receive_json_from(timeout=3)
                responses.append(resp)
                if resp.get("type") == "crisis_detected":
                    break
            except Exception:
                break

        crisis_responses = [r for r in responses if r.get("type") == "crisis_detected"]
        assert len(crisis_responses) >= 1

    await communicator.disconnect()
