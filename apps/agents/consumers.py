"""WebSocket consumers for real-time agent chat and support group."""

import json
import logging
import time
from typing import Any

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.agents.models import AgentAuditLog
from apps.agents.services import ContextService, ConversationService
from apps.agents.workflow import get_workflow
from apps.patients.models import Patient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared auth mixin for patient-facing consumers.
# Fixes IDOR gap: verifies session patient_id matches URL patient_id.
# ---------------------------------------------------------------------------


class PatientWebSocketMixin:
    """Shared authentication for patient-facing WebSocket consumers."""

    async def authenticate_patient(self) -> bool:
        """Verify the connecting user owns this patient_id.

        Returns True if authenticated, False if rejected.
        """
        self.patient_id = self.scope["url_route"]["kwargs"].get("patient_id")

        # Check session has a patient_id and it matches the URL
        session = self.scope.get("session", {})
        session_patient_id = session.get("patient_id")
        if session_patient_id and str(session_patient_id) != str(self.patient_id):
            logger.warning(
                "WebSocket IDOR: session patient_id=%s != URL patient_id=%s",
                session_patient_id,
                self.patient_id,
            )
            return False

        # Verify patient exists
        self.patient = await self._get_patient(self.patient_id)
        return bool(self.patient)

    @database_sync_to_async
    def _get_patient(self, patient_id: str) -> Patient | None:
        try:
            return Patient.objects.select_related("user", "preferences").get(id=patient_id)
        except Patient.DoesNotExist:
            return None


class AgentChatConsumer(PatientWebSocketMixin, AsyncWebsocketConsumer):
    """WebSocket consumer for patient-agent chat."""

    async def connect(self):
        """Handle WebSocket connection."""
        if not await self.authenticate_patient():
            await self.close()
            return

        self.room_group_name = f"patient_{self.patient_id}"

        # Join patient-specific group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()
        logger.info(f"WebSocket connected for patient {self.patient_id}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )
            logger.info(f"WebSocket disconnected for patient {self.patient_id}")

    async def receive(self, text_data):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(text_data)
            message = data.get("message", "").strip()

            if not message:
                await self.send_error("Message cannot be empty")
                return

            # Process message through agent workflow
            result = await self.process_message(message)

            # Send response back to client
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "agent_response",
                        "message": result["response"],
                        "agent_type": result["agent_type"],
                        "escalate": result["escalate"],
                        "metadata": result.get("metadata", {}),
                    }
                )
            )

            # Broadcast to clinician dashboard if escalation
            if result["escalate"]:
                await self.broadcast_escalation(result)

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send_error("Internal error")

    async def process_message(self, message: str) -> dict[str, Any]:
        """Process message through agent workflow.

        Args:
            message: Patient's message

        Returns:
            Workflow result
        """
        # Get or create conversation
        conversation = await database_sync_to_async(ConversationService.get_or_create_conversation)(self.patient)

        # Add user message
        await database_sync_to_async(ConversationService.add_message)(
            conversation=conversation,
            role="user",
            content=message,
        )

        # Assemble context
        context = await database_sync_to_async(ContextService.assemble_full_context)(self.patient, conversation)

        # Process through workflow
        workflow = get_workflow()
        result = await workflow.process_message(message, context)

        # Add agent response
        await database_sync_to_async(ConversationService.add_message)(
            conversation=conversation,
            role="assistant",
            content=result["response"],
            agent_type=result["agent_type"],
            confidence_score=result.get("metadata", {}).get("confidence"),
            escalation_triggered=result["escalate"],
            escalation_reason=result.get("escalation_reason", ""),
            metadata=result.get("metadata", {}),
        )

        # Update conversation status if escalated
        if result["escalate"]:
            await database_sync_to_async(ConversationService.update_conversation_status)(
                conversation=conversation,
                status="escalated",
                escalation_reason=result.get("escalation_reason", ""),
            )

            # Create escalation record
            from apps.agents.services import EscalationService

            await database_sync_to_async(EscalationService.create_escalation)(
                patient=self.patient,
                conversation=conversation,
                reason=result.get("escalation_reason", "Unknown"),
                severity=result.get("metadata", {}).get("severity", "urgent"),
                conversation_summary=result["response"],
                patient_context=context.get("patient", {}),
            )

        # Log audit event
        await self.log_audit_event(
            action="message_processed",
            agent_type=result["agent_type"],
            details={
                "message": message[:200],
                "response": result["response"][:200],
                "escalated": result["escalate"],
            },
        )

        return result

    async def broadcast_escalation(self, result: dict[str, Any]):
        """Broadcast escalation to clinician dashboard.

        Args:
            result: Workflow result with escalation info
        """
        # Broadcast to hospital-specific group
        hospital_group = f"hospital_{self.patient.hospital_id}"

        await self.channel_layer.group_send(
            hospital_group,
            {
                "type": "escalation_alert",
                "patient_id": str(self.patient.id),
                "patient_name": f"{self.patient.user.first_name} {self.patient.user.last_name}",
                "severity": result.get("metadata", {}).get("severity", "urgent"),
                "reason": result.get("escalation_reason", ""),
                "timestamp": result.get("timestamp", ""),
            },
        )

    async def escalation_alert(self, event):
        """Handle escalation alert from channel layer."""
        # Send to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "escalation_alert",
                    "data": event,
                }
            )
        )

    async def send_error(self, error_message: str):
        """Send error message to client.

        Args:
            error_message: Error message
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "error",
                    "message": error_message,
                }
            )
        )

    @database_sync_to_async
    def log_audit_event(
        self,
        action: str,
        agent_type: str,
        details: dict[str, Any],
    ):
        """Log audit event.

        Args:
            action: Action name
            agent_type: Agent type
            details: Event details
        """
        try:
            AgentAuditLog.objects.create(
                patient=self.patient,
                action=action,
                agent_type=agent_type,
                details=details,
                ip_address=self.scope.get("client", [None])[0],
                user_agent=self.scope.get("headers", {}).get(b"user-agent", b"").decode(),
            )
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")


class ClinicianDashboardConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for clinician dashboard."""

    async def connect(self):
        """Handle WebSocket connection with clinician auth verification."""
        self.hospital_id = self.scope["url_route"]["kwargs"].get("hospital_id")
        self.room_group_names = []

        # Verify user is authenticated clinician with access to this hospital
        user = self.scope.get("user")
        if not user or not user.is_authenticated or user.role != "clinician":
            logger.warning("WebSocket auth rejected: user not an authenticated clinician")
            return

        try:
            clinician = await sync_to_async(lambda: user.clinician_profile)()
            if not clinician.is_active:
                return

            # Verify hospital access — Hospital uses int PK
            hospital_ids = await sync_to_async(lambda: set(clinician.hospitals.values_list("id", flat=True)))()

            if int(self.hospital_id) not in hospital_ids:
                logger.warning(
                    "WebSocket IDOR: clinician=%s tried hospital=%s",
                    clinician.id,
                    self.hospital_id,
                )
                return
        except Exception:
            logger.warning("WebSocket auth failed: no clinician profile")
            return

        # Join ALL hospital groups the clinician has access to so they
        # receive broadcasts for patients at any of their hospitals.
        for hid in hospital_ids:
            group_name = f"hospital_{hid}"
            self.room_group_names.append(group_name)
            await self.channel_layer.group_add(group_name, self.channel_name)

        await self.accept()
        logger.info(
            "Clinician dashboard connected for hospitals %s",
            [int(h) for h in hospital_ids],
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        for group_name in getattr(self, "room_group_names", []):
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def escalation_alert(self, event):
        """Handle escalation alert."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "escalation_alert",
                    "patient_id": event["patient_id"],
                    "patient_name": event["patient_name"],
                    "severity": event["severity"],
                    "reason": event["reason"],
                    "timestamp": event["timestamp"],
                }
            )
        )

    async def patient_status_update(self, event):
        """Handle patient status update."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "patient_status_update",
                    "patient_id": event["patient_id"],
                    "old_status": event["old_status"],
                    "new_status": event["new_status"],
                    "timestamp": event["timestamp"],
                }
            )
        )

    async def patient_message(self, event):
        """Handle new patient message (for clinicians with take-control)."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "patient_message",
                    "patient_id": event["patient_id"],
                    "message": event["message"],
                }
            )
        )


# ---------------------------------------------------------------------------
# Support Group Consumer
# ---------------------------------------------------------------------------


class SupportGroupConsumer(PatientWebSocketMixin, AsyncWebsocketConsumer):
    """WebSocket consumer for support group chat. Full bidirectional."""

    async def connect(self):
        if not await self.authenticate_patient():
            await self.close()
            return

        self.room_group_name = f"support_group_{self.patient_id}"
        self._last_message_time = 0

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()
        logger.info(f"Support group WS connected for patient {self.patient_id}")

        # Send conversation history so page reloads restore the chat
        await self._send_history()

    async def _send_history(self):
        """Send existing conversation messages + reactions on connect."""
        history = await self._load_history()
        if history:
            await self.send_json({"type": "history", "messages": history})

    @database_sync_to_async
    def _load_history(self):
        """Load existing support group messages with reactions."""
        from apps.agents.models import AgentConversation, AgentMessage

        try:
            conversation = AgentConversation.objects.get(
                patient=self.patient,
                conversation_type="support_group",
            )
        except AgentConversation.DoesNotExist:
            return []

        messages = (
            AgentMessage.objects.filter(conversation=conversation)
            .prefetch_related("reactions")
            .order_by("created_at")[:100]
        )

        from apps.agents.personas import PERSONA_REGISTRY

        result = []
        for msg in messages:
            if msg.role == "user":
                entry = {
                    "type": "user",
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                }
                meta = msg.metadata or {}
                if meta.get("channel") == "voice":
                    entry["channel"] = "voice"
                    if meta.get("audio_url"):
                        entry["audio_url"] = meta["audio_url"]
                result.append(entry)
            elif msg.persona_id:
                persona = PERSONA_REGISTRY.get(msg.persona_id)
                entry = {
                    "type": "persona",
                    "message_id": str(msg.id),
                    "persona_id": msg.persona_id,
                    "persona_name": persona.name if persona else msg.persona_id,
                    "content": msg.content,
                    "avatar_color": persona.avatar_color if persona else "#6B7280",
                    "avatar_color_dark": persona.avatar_color_dark if persona else "#9CA3AF",
                    "avatar_initials": persona.avatar_initials if persona else "??",
                    "reactions": [
                        {"persona_id": r.persona_id, "emoji": r.emoji, "timestamp": r.created_at.isoformat()}
                        for r in msg.reactions.all().order_by("created_at")
                    ],
                    "timestamp": msg.created_at.isoformat(),
                }
                result.append(entry)
        return result

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

    async def receive(self, text_data):
        """Handle incoming patient message."""
        from apps.agents.constants import SG_RATE_LIMIT_SECONDS

        try:
            data = json.loads(text_data)
            message = data.get("message", "").strip()

            if not message:
                await self.send_json({"type": "error", "message": "Message cannot be empty"})
                return

            # Rate limiting
            now = time.monotonic()
            if now - self._last_message_time < SG_RATE_LIMIT_SECONDS:
                await self.send_json({"type": "error", "message": "Please wait a moment"})
                return
            self._last_message_time = now

            # Get or create support group conversation
            conversation = await self._get_or_create_conversation()

            # Save patient message
            await self._save_user_message(conversation, message, data)

            # Send typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "support_group_typing", "persona_id": "", "persona_name": ""},
            )

            # Process through orchestrator
            from apps.agents.support_group import SupportGroupOrchestrator

            orchestrator = SupportGroupOrchestrator()
            result = await orchestrator.process_message(self.patient, conversation, message)

            if result.get("escalate"):
                # Send escalation banner
                await self.send_json(
                    {
                        "type": "crisis_detected",
                        "message": "Your care team has been notified and will follow up shortly.",
                    }
                )
                # Notify clinician dashboard
                await self._broadcast_escalation()
            else:
                # Push primary persona response to the group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "support_group_message",
                        **result,
                    },
                )

        except json.JSONDecodeError:
            await self.send_json({"type": "error", "message": "Invalid JSON"})
        except Exception as e:
            logger.error(f"Support group error: {e}", exc_info=True)
            await self.send_json({"type": "error", "message": "Something went wrong"})

    # -- Channel layer event handlers --

    async def support_group_message(self, event):
        """Push a persona message to the client."""
        await self.send_json(
            {
                "type": "support_group_message",
                "message_id": event.get("message_id"),
                "persona_id": event.get("persona_id"),
                "persona_name": event.get("persona_name"),
                "content": event.get("content"),
                "avatar_color": event.get("avatar_color"),
                "avatar_color_dark": event.get("avatar_color_dark"),
                "avatar_initials": event.get("avatar_initials"),
            }
        )

    async def support_group_reaction(self, event):
        """Push an emoji reaction to the client."""
        await self.send_json(
            {
                "type": "support_group_reaction",
                "message_id": event.get("message_id"),
                "persona_id": event.get("persona_id"),
                "emoji": event.get("emoji"),
                "timestamp": event.get("timestamp", ""),
            }
        )

    async def support_group_typing(self, event):
        """Push typing indicator to the client."""
        await self.send_json(
            {
                "type": "support_group_typing",
                "persona_id": event.get("persona_id"),
                "persona_name": event.get("persona_name"),
            }
        )

    # -- Helpers --

    async def send_json(self, data):
        await self.send(text_data=json.dumps(data))

    @database_sync_to_async
    def _get_or_create_conversation(self):
        return ConversationService.get_or_create_conversation(
            self.patient,
            conversation_type="support_group",
        )

    @database_sync_to_async
    def _save_user_message(self, conversation, message, data):
        from apps.agents.models import AgentMessage

        metadata = {}
        if data.get("channel") == "voice":
            metadata["channel"] = "voice"
            if data.get("audio_url"):
                metadata["audio_url"] = data["audio_url"]

        return AgentMessage.objects.create(
            conversation=conversation,
            role="user",
            content=message,
            metadata=metadata,
        )

    async def _broadcast_escalation(self):
        """Notify clinician dashboard of support group escalation."""
        hospital_group = f"hospital_{self.patient.hospital_id}"
        await self.channel_layer.group_send(
            hospital_group,
            {
                "type": "escalation_alert",
                "patient_id": str(self.patient.id),
                "patient_name": f"{self.patient.user.first_name} {self.patient.user.last_name}",
                "severity": "critical",
                "reason": "Support group crisis detected",
                "timestamp": "",
            },
        )
