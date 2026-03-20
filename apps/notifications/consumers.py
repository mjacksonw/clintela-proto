"""WebSocket consumer for real-time notifications.

Groups:
    patient_{id}_notifications  — patient-facing notifications
    clinician_{id}_notifications — clinician-facing notifications

Events:
    notification.new       — new notification created
    notification.read      — notification marked as read
    delivery.status_update — delivery status changed (✓ → ✓✓)
"""

import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for patient notifications."""

    async def connect(self):
        self.patient_id = self.scope["url_route"]["kwargs"].get("patient_id")
        self.group_name = f"patient_{self.patient_id}_notifications"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send unread count on connect
        count = await self._get_unread_count()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "unread_count",
                    "count": count,
                }
            )
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle client messages (mark_read)."""
        try:
            data = json.loads(text_data)
            if data.get("action") == "mark_read":
                notification_id = data.get("notification_id")
                if notification_id:
                    await self._mark_read(notification_id)
                    count = await self._get_unread_count()
                    await self.send(
                        text_data=json.dumps(
                            {
                                "type": "notification.read",
                                "notification_id": notification_id,
                                "unread_count": count,
                            }
                        )
                    )
        except (json.JSONDecodeError, KeyError):
            pass

    async def notification_new(self, event):
        """Handle new notification from channel layer."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification.new",
                    "notification": event["notification"],
                    "unread_count": event.get("unread_count", 0),
                }
            )
        )

    async def notification_read(self, event):
        """Handle notification read event."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification.read",
                    "notification_id": event["notification_id"],
                    "unread_count": event.get("unread_count", 0),
                }
            )
        )

    async def delivery_status_update(self, event):
        """Handle delivery status update (✓ → ✓✓)."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "delivery.status_update",
                    "notification_id": event["notification_id"],
                    "channel": event["channel"],
                    "status": event["status"],
                }
            )
        )

    @database_sync_to_async
    def _get_unread_count(self):
        from apps.notifications.models import Notification

        return Notification.objects.filter(patient_id=self.patient_id, is_read=False).count()

    @database_sync_to_async
    def _mark_read(self, notification_id):
        from apps.notifications.services import NotificationService

        NotificationService.mark_read(notification_id)


class ClinicianNotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for clinician notifications."""

    async def connect(self):
        self.clinician_id = self.scope["url_route"]["kwargs"].get("clinician_id")
        self.group_name = f"clinician_{self.clinician_id}_notifications"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification_new(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification.new",
                    "notification": event["notification"],
                }
            )
        )

    async def delivery_status_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "delivery.status_update",
                    "notification_id": event["notification_id"],
                    "channel": event["channel"],
                    "status": event["status"],
                }
            )
        )
