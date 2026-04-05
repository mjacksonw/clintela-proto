"""Tests for PatientWebSocketMixin authentication logic."""

import pytest
from channels.db import database_sync_to_async

from apps.agents.consumers import PatientWebSocketMixin
from apps.agents.tests.factories import PatientFactory

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Helper: instantiate the mixin with a fake scope
# ---------------------------------------------------------------------------


def _build_mixin(patient_id, session=None):
    """Create a PatientWebSocketMixin instance with the given scope."""
    mixin = PatientWebSocketMixin()
    mixin.scope = {
        "url_route": {"kwargs": {"patient_id": str(patient_id)}},
        "session": session or {},
    }
    return mixin


# ==========================================================================
# Tests
# ==========================================================================


async def test_mixin_auth_success():
    """Session matches URL -> returns True and sets self.patient."""
    patient = await database_sync_to_async(PatientFactory)()

    mixin = _build_mixin(patient.id, session={"patient_id": str(patient.id)})
    result = await mixin.authenticate_patient()

    assert result is True
    assert mixin.patient is not None
    assert mixin.patient.id == patient.id


async def test_mixin_auth_failure_no_session():
    """No patient_id in session, non-existent patient -> returns False."""
    # Use an ID that doesn't exist in DB
    mixin = _build_mixin(999999, session={})

    result = await mixin.authenticate_patient()

    # No session patient_id: IDOR check is skipped.
    # But patient 999999 doesn't exist, so _get_patient returns None -> False
    assert result is False


async def test_mixin_auth_failure_mismatch():
    """Session patient_id != URL patient_id -> returns False (IDOR block)."""
    patient = await database_sync_to_async(PatientFactory)()
    other_patient = await database_sync_to_async(PatientFactory)()

    mixin = _build_mixin(patient.id, session={"patient_id": str(other_patient.id)})
    result = await mixin.authenticate_patient()

    assert result is False
