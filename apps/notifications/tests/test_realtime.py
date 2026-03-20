"""Tests for real-time notification delivery via channel layer."""

from unittest.mock import MagicMock, patch

import pytest

from apps.agents.tests.factories import PatientFactory
from apps.notifications.services import _push_notification_to_websocket


@pytest.mark.django_db
class TestRealtimePush:
    @patch("channels.layers.get_channel_layer")
    def test_push_notification_sends_to_patient_group(self, mock_get_layer):
        patient = PatientFactory()

        mock_layer = MagicMock()
        mock_get_layer.return_value = mock_layer

        # Mock the group_send to be a regular function
        sent_messages = []

        def fake_group_send(group, message):
            sent_messages.append((group, message))

        mock_layer.group_send = fake_group_send

        from apps.notifications.models import Notification

        notification = Notification.objects.create(
            patient=patient,
            notification_type="alert",
            severity="info",
            title="Test",
            message="Test message",
        )

        _push_notification_to_websocket(notification)

        assert len(sent_messages) == 1
        group_name, message = sent_messages[0]
        assert group_name == f"patient_{patient.id}_notifications"
        assert message["type"] == "notification.new"
        assert message["notification"]["title"] == "Test"

    def test_push_handles_no_channel_layer(self):
        """Push doesn't raise when channel layer is None."""
        notification = MagicMock()
        notification.patient_id = 123
        notification.clinician_id = None
        notification.id = 1
        notification.notification_type = "alert"
        notification.severity = "info"
        notification.title = "Test"
        notification.message = "Test"
        notification.is_read = False
        notification.created_at = None

        with patch("channels.layers.get_channel_layer", return_value=None):
            # Should not raise
            _push_notification_to_websocket(notification)

    def test_push_handles_channel_layer_error(self):
        """Push doesn't raise when channel layer throws."""
        notification = MagicMock()
        notification.patient_id = 456
        notification.clinician_id = None

        with patch("channels.layers.get_channel_layer", side_effect=Exception("fail")):
            # Should not raise
            _push_notification_to_websocket(notification)
