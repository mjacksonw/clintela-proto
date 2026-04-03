"""API endpoints for mobile push notification device management.

Endpoints:
    POST /api/v1/devices/register/   — register a push token after app install
    DELETE /api/v1/devices/{token}/   — remove a push token on logout/uninstall
"""

import logging

from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.notifications.models import DeviceToken

logger = logging.getLogger(__name__)

router = Router(tags=["devices"])


class DeviceRegisterRequest(Schema):
    """Request schema for push token registration."""

    token: str
    platform: str  # "ios" or "android"
    device_name: str = ""


class DeviceRegisterResponse(Schema):
    """Response schema for push token registration."""

    id: int
    token: str
    platform: str
    device_name: str
    is_active: bool
    created: bool  # True if new, False if re-activated


class DeviceDeleteResponse(Schema):
    """Response schema for push token deletion."""

    deactivated: bool


@router.post("/register/", response=DeviceRegisterResponse)
def register_device(request, data: DeviceRegisterRequest):
    """Register a push notification token for the authenticated patient.

    Idempotent: re-registering the same token reactivates it.
    """
    session = request.session
    patient_id = session.get("patient_id")
    if not session.get("authenticated") or not patient_id:
        raise HttpError(401, "Authentication required")

    if data.platform not in ("ios", "android"):
        raise HttpError(400, "Platform must be 'ios' or 'android'")

    if not data.token or len(data.token) > 255:
        raise HttpError(400, "Invalid token")

    from apps.patients.models import Patient

    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist as exc:
        raise HttpError(404, "Patient not found") from exc

    # Idempotent: update_or_create on token
    device, created = DeviceToken.objects.update_or_create(
        token=data.token,
        defaults={
            "patient": patient,
            "platform": data.platform,
            "device_name": data.device_name,
            "is_active": True,
            "deactivated_at": None,
        },
    )

    logger.info(
        "Device token %s",
        "registered" if created else "re-activated",
        extra={"device_id": device.id, "patient_id": patient_id, "platform": data.platform},
    )

    return DeviceRegisterResponse(
        id=device.id,
        token=device.token,
        platform=device.platform,
        device_name=device.device_name,
        is_active=device.is_active,
        created=created,
    )


@router.delete("/{token}/", response=DeviceDeleteResponse)
def delete_device(request, token: str):
    """Deactivate a push notification token.

    Scoped to the authenticated patient to prevent IDOR.
    """
    session = request.session
    patient_id = session.get("patient_id")
    if not session.get("authenticated") or not patient_id:
        raise HttpError(401, "Authentication required")

    updated = DeviceToken.objects.filter(
        token=token,
        patient_id=patient_id,
        is_active=True,
    ).update(
        is_active=False,
        deactivated_at=timezone.now(),
    )

    if updated == 0:
        raise HttpError(404, "Device token not found or already deactivated")

    logger.info(
        "Device token deactivated",
        extra={"token_prefix": token[:8], "patient_id": patient_id},
    )

    return DeviceDeleteResponse(deactivated=True)
