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
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for patient notifications."""

    async def connect(self):
        self.patient_id = self.scope["url_route"]["kwargs"].get("patient_id")
        self.group_name = f"patient_{self.patient_id}_notifications"

        # Auth check: verify session patient matches requested patient_id
        session = self.scope.get("session", {})
        session_patient_id = session.get("patient_id")
        if not session.get("authenticated") or str(session_patient_id) != str(self.patient_id):
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Update last_active_at on connect
        await self._update_last_active()

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
            action = data.get("action")

            if action == "mark_read":
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
            elif action == "heartbeat":
                await self._update_last_active()
                await self.send(text_data=json.dumps({"type": "heartbeat.ack"}))
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

    async def chat_message(self, event):
        """Handle clinician chat message pushed to patient."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat.message",
                    "message": event["message"],
                }
            )
        )

    @database_sync_to_async
    def _get_unread_count(self):
        from apps.notifications.models import Notification

        return Notification.objects.filter(patient_id=self.patient_id, is_read=False).count()

    @database_sync_to_async
    def _mark_read(self, notification_id):
        """Mark notification as read, scoped to this patient to prevent IDOR."""
        from apps.notifications.models import Notification

        Notification.objects.filter(
            id=notification_id,
            patient_id=self.patient_id,
        ).update(is_read=True)

    @database_sync_to_async
    def _update_last_active(self):
        """Update last_active_at on the patient's User record.

        Called on connect and on every heartbeat (client sends every 30s).
        Used by notification routing to suppress push when WS is active.
        """
        from apps.accounts.models import User
        from apps.patients.models import Patient

        try:
            patient = Patient.objects.select_related("user").get(id=self.patient_id)
            User.objects.filter(id=patient.user_id).update(last_active_at=timezone.now())
        except Patient.DoesNotExist:
            pass


class ClinicianNotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for clinician notifications."""

    async def connect(self):
        self.clinician_id = self.scope["url_route"]["kwargs"].get("clinician_id")
        self.group_name = f"clinician_{self.clinician_id}_notifications"

        # Auth check: verify the connecting user is the clinician
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        # Clinician has its own PK — look up via user FK
        from apps.clinicians.models import Clinician

        try:
            clinician = await Clinician.objects.aget(user=user)
            if str(clinician.id) != str(self.clinician_id):
                await self.close()
                return
        except Clinician.DoesNotExist:
            await self.close()
            return

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
