"""WebSocket consumer for real-time agent chat."""

import json
import logging
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from apps.agents.models import AgentAuditLog
from apps.agents.services import ContextService, ConversationService
from apps.agents.workflow import get_workflow
from apps.patients.models import Patient

logger = logging.getLogger(__name__)


class AgentChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for patient-agent chat."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.patient_id = self.scope["url_route"]["kwargs"].get("patient_id")
        self.room_group_name = f"patient_{self.patient_id}"

        # Verify patient exists and user has access
        self.patient = await self.get_patient(self.patient_id)
        if not self.patient:
            await self.close()
            return

        # Join patient-specific group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()
        logger.info(f"WebSocket connected for patient {self.patient_id}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave room group
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
            await self.send(text_data=json.dumps({
                "type": "agent_response",
                "message": result["response"],
                "agent_type": result["agent_type"],
                "escalate": result["escalate"],
                "metadata": result.get("metadata", {}),
            }))

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
        conversation = await database_sync_to_async(
            ConversationService.get_or_create_conversation
        )(self.patient)

        # Add user message
        await database_sync_to_async(ConversationService.add_message)(
            conversation=conversation,
            role="user",
            content=message,
        )

        # Assemble context
        context = await database_sync_to_async(
            ContextService.assemble_full_context
        )(self.patient, conversation)

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
            await database_sync_to_async(
                ConversationService.update_conversation_status
            )(
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
                "patient_name": f"{self.patient.first_name} {self.patient.last_name}",
                "severity": result.get("metadata", {}).get("severity", "urgent"),
                "reason": result.get("escalation_reason", ""),
                "timestamp": result.get("timestamp", ""),
            },
        )

    async def escalation_alert(self, event):
        """Handle escalation alert from channel layer."""
        # Send to WebSocket
        await self.send(text_data=json.dumps({
            "type": "escalation_alert",
            "data": event,
        }))

    async def send_error(self, error_message: str):
        """Send error message to client.

        Args:
            error_message: Error message
        """
        await self.send(text_data=json.dumps({
            "type": "error",
            "message": error_message,
        }))

    @database_sync_to_async
    def get_patient(self, patient_id: str) -> Patient | None:
        """Get patient by ID.

        Args:
            patient_id: Patient UUID string

        Returns:
            Patient instance or None
        """
        try:
            return Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            return None

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
        """Handle WebSocket connection."""
        self.hospital_id = self.scope["url_route"]["kwargs"].get("hospital_id")
        self.room_group_name = f"hospital_{self.hospital_id}"

        # TODO: Verify user is authenticated clinician
        # For now, accept all connections

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()
        logger.info(f"Clinician dashboard connected for hospital {self.hospital_id}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def escalation_alert(self, event):
        """Handle escalation alert."""
        await self.send(text_data=json.dumps({
            "type": "escalation",
            "patient_id": event["patient_id"],
            "patient_name": event["patient_name"],
            "severity": event["severity"],
            "reason": event["reason"],
            "timestamp": event["timestamp"],
        }))

    async def patient_status_update(self, event):
        """Handle patient status update."""
        await self.send(text_data=json.dumps({
            "type": "status_update",
            "patient_id": event["patient_id"],
            "old_status": event["old_status"],
            "new_status": event["new_status"],
            "timestamp": event["timestamp"],
        }))
