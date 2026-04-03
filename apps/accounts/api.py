"""API endpoints for auth status (mobile app AuthBridge).

Endpoints:
    GET /api/v1/auth/status/  — lightweight session check for native screens
"""

import contextlib
import logging

from ninja import Router, Schema

logger = logging.getLogger(__name__)

router = Router(tags=["auth"])


class AuthStatusResponse(Schema):
    """Response schema for auth status check."""

    authenticated: bool
    patient_id: str | None = None
    expires_at: str | None = None
    preferred_name: str | None = None


@router.get("/status/", response=AuthStatusResponse)
def auth_status(request):
    """Check if the current session is authenticated.

    Used by the mobile app's AuthBridge plugin to validate session
    state before native screen transitions. Lightweight — no DB queries
    unless authenticated.
    """
    session = request.session
    patient_id = session.get("patient_id")
    is_authenticated = bool(session.get("authenticated") and patient_id)

    if not is_authenticated:
        return AuthStatusResponse(authenticated=False)

    # Get preferred name if available
    preferred_name = None
    with contextlib.suppress(Exception):
        from apps.patients.models import Patient

        patient = Patient.objects.select_related("user").get(id=patient_id)
        preferred_name = patient.user.first_name or None
        if hasattr(patient, "preferences") and patient.preferences.preferred_name:
            preferred_name = patient.preferences.preferred_name

    # Session expiry
    expires_at = None
    if hasattr(session, "get_expiry_date"):
        with contextlib.suppress(Exception):
            expires_at = session.get_expiry_date().isoformat()

    return AuthStatusResponse(
        authenticated=True,
        patient_id=str(patient_id),
        expires_at=expires_at,
        preferred_name=preferred_name,
    )
