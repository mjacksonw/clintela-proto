"""API endpoints for agent system."""

import json
from typing import Any

from ninja import Router
from ninja.errors import HttpError

from apps.agents.models import AgentConversation, Escalation
from apps.agents.schemas import (
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    EscalationListResponse,
    EscalationResponse,
)
from apps.agents.services import (
    ContextService,
    ConversationService,
    EscalationService,
)
from apps.agents.workflow import get_workflow
from apps.patients.models import Patient

router = Router(tags=["agents"])


@router.post("/chat/{patient_id}", response=ChatMessageResponse)
async def send_chat_message(request, patient_id: str, data: ChatMessageRequest):
    """Send a chat message to the agent system.

    Args:
        request: HTTP request
        patient_id: Patient UUID
        data: Chat message request

    Returns:
        ChatMessageResponse with agent response
    """
    message = data.message.strip()

    if not message:
        raise HttpError(400, "Message cannot be empty")

    # Get patient
    patient = await get_patient_async(patient_id)
    if not patient:
        raise HttpError(404, "Patient not found")

    # Get or create conversation
    conversation = await get_conversation_async(patient)

    # Add user message
    await add_message_async(
        conversation=conversation,
        role="user",
        content=message,
    )

    # Assemble context
    context = await get_context_async(patient, conversation)

    # Process through workflow
    workflow = get_workflow()
    result = await workflow.process_message(message, context)

    # Add agent response
    await add_message_async(
        conversation=conversation,
        role="assistant",
        content=result["response"],
        agent_type=result["agent_type"],
        confidence_score=result.get("metadata", {}).get("confidence"),
        escalation_triggered=result["escalate"],
        escalation_reason=result.get("escalation_reason", ""),
        metadata=result.get("metadata", {}),
    )

    # Handle escalation
    if result["escalate"]:
        await handle_escalation_async(
            patient=patient,
            conversation=conversation,
            result=result,
            context=context,
        )

    return ChatMessageResponse(
        response=result["response"],
        agent_type=result["agent_type"],
        escalate=result["escalate"],
        escalation_reason=result.get("escalation_reason", ""),
        conversation_id=str(conversation.id),
    )


@router.get("/chat/{patient_id}/history", response=ChatHistoryResponse)
async def get_chat_history(
    request,
    patient_id: str,
    page: int = 1,
    page_size: int = 20,
):
    """Get chat history for a patient.

    Args:
        request: HTTP request
        patient_id: Patient UUID
        page: Page number
        page_size: Items per page

    Returns:
        ChatHistoryResponse with paginated messages
    """
    patient = await get_patient_async(patient_id)
    if not patient:
        raise HttpError(404, "Patient not found")

    # Get active conversation
    conversation = await get_conversation_async(patient, create=False)

    if not conversation:
        return ChatHistoryResponse(
            messages=[],
            total=0,
            page=page,
            page_size=page_size,
        )

    # Get messages
    messages = await get_messages_async(conversation, page, page_size)

    return ChatHistoryResponse(
        messages=messages,
        total=await get_message_count_async(conversation),
        page=page,
        page_size=page_size,
    )


@router.get("/escalations", response=EscalationListResponse)
async def list_escalations(
    request,
    status: str = "pending",
    hospital_id: int | None = None,
    severity: str | None = None,
):
    """List escalations for clinicians.

    Args:
        request: HTTP request
        status: Filter by status (pending, acknowledged, resolved)
        hospital_id: Filter by hospital
        severity: Filter by severity (critical, urgent, routine)

    Returns:
        EscalationListResponse with escalations
    """
    escalations = await get_escalations_async(
        status=status,
        hospital_id=hospital_id,
        severity=severity,
    )

    return EscalationListResponse(
        escalations=[
            EscalationResponse(
                id=str(esc.id),
                patient_id=str(esc.patient.id),
                patient_name=f"{esc.patient.first_name} {esc.patient.last_name}",
                reason=esc.reason,
                severity=esc.severity,
                status=esc.status,
                created_at=esc.created_at.isoformat(),
                conversation_summary=esc.conversation_summary[:200] if esc.conversation_summary else "",
            )
            for esc in escalations
        ],
        total=len(escalations),
    )


@router.post("/escalations/{escalation_id}/acknowledge")
async def acknowledge_escalation(request, escalation_id: str):
    """Acknowledge an escalation.

    Args:
        request: HTTP request
        escalation_id: Escalation UUID

    Returns:
        Success response
    """
    # FIXME: Implement proper authentication
    # For now, require a clinician_id in the request body
    # In production, this should come from request.user
    clinician_id = getattr(request, "user", None)
    if clinician_id and hasattr(clinician_id, "id"):
        clinician_id = clinician_id.id
    else:
        # Temporary: accept from request body for testing
        try:
            body = json.loads(request.body)
            clinician_id = body.get("clinician_id")
        except (json.JSONDecodeError, AttributeError):
            clinician_id = None

    if not clinician_id:
        raise HttpError(401, "Authentication required")

    success = await acknowledge_escalation_async(escalation_id, clinician_id)

    if not success:
        raise HttpError(404, "Escalation not found")

    return {"success": True, "message": "Escalation acknowledged"}


@router.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation(request, escalation_id: str):
    """Resolve an escalation.

    Args:
        request: HTTP request
        escalation_id: Escalation UUID

    Returns:
        Success response
    """
    success = await resolve_escalation_async(escalation_id)

    if not success:
        raise HttpError(404, "Escalation not found")

    return {"success": True, "message": "Escalation resolved"}


# Async helper functions



async def get_patient_async(patient_id: str) -> Patient | None:
    """Get patient by ID asynchronously."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _get():
        try:
            return Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            return None

    return await _get()


async def get_conversation_async(
    patient: Patient,
    create: bool = True,
) -> AgentConversation | None:
    """Get or create conversation asynchronously."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _get():
        if create:
            return ConversationService.get_or_create_conversation(patient)
        return AgentConversation.objects.filter(
            patient=patient,
            status="active",
        ).first()

    return await _get()


async def add_message_async(
    conversation: AgentConversation,
    role: str,
    content: str,
    **kwargs,
):
    """Add message to conversation asynchronously."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _add():
        return ConversationService.add_message(
            conversation=conversation,
            role=role,
            content=content,
            **kwargs,
        )

    await _add()


async def get_context_async(
    patient: Patient,
    conversation: AgentConversation,
) -> dict[str, Any]:
    """Get context asynchronously."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _get():
        return ContextService.assemble_full_context(patient, conversation)

    return await _get()


async def handle_escalation_async(
    patient: Patient,
    conversation: AgentConversation,
    result: dict[str, Any],
    context: dict[str, Any],
):
    """Handle escalation asynchronously."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _handle():
        # Update conversation status
        ConversationService.update_conversation_status(
            conversation=conversation,
            status="escalated",
            escalation_reason=result.get("escalation_reason", ""),
        )

        # Create escalation record
        EscalationService.create_escalation(
            patient=patient,
            conversation=conversation,
            reason=result.get("escalation_reason", "Unknown"),
            severity=result.get("metadata", {}).get("severity", "urgent"),
            conversation_summary=result["response"],
            patient_context=context.get("patient", {}),
        )

    await _handle()


async def get_messages_async(
    conversation: AgentConversation,
    page: int,
    page_size: int,
) -> list[dict[str, Any]]:
    """Get messages asynchronously."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _get():
        messages = ConversationService.get_conversation_history(
            conversation,
            limit=page_size * page,
        )
        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        return messages[start:end]

    return await _get()


async def get_message_count_async(conversation: AgentConversation) -> int:
    """Get message count asynchronously."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _count():
        return conversation.messages.count()

    return await _count()


async def get_escalations_async(
    status: str,
    hospital_id: int | None,
    severity: str | None,
) -> list[Escalation]:
    """Get escalations asynchronously."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _get():
        queryset = Escalation.objects.filter(status=status)

        if hospital_id:
            queryset = queryset.filter(patient__hospital_id=hospital_id)

        if severity:
            queryset = queryset.filter(severity=severity)

        return list(queryset.select_related("patient").order_by("-created_at")[:50])

    return await _get()


async def acknowledge_escalation_async(
    escalation_id: str,
    clinician_id: int,
) -> bool:
    """Acknowledge escalation asynchronously."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _ack():
        return EscalationService.acknowledge_escalation(escalation_id, clinician_id)

    return await _ack()


async def resolve_escalation_async(escalation_id: str) -> bool:
    """Resolve escalation asynchronously."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _resolve():
        return EscalationService.resolve_escalation(escalation_id)

    return await _resolve()
