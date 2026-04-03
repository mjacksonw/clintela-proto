"""API endpoints for mobile health data sync.

Endpoints:
    POST /api/v1/health/sync/  — batch ingest from HealthKit / Health Connect
"""

import logging
from datetime import datetime

from django.db import IntegrityError
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.clinical.constants import VALID_CONCEPT_IDS

logger = logging.getLogger(__name__)

router = Router(tags=["health"])


class HealthObservationItem(Schema):
    """Single health observation from HealthKit / Health Connect."""

    concept_id: int
    value_numeric: float | None = None
    value_text: str = ""
    unit: str = ""
    observed_at: str  # ISO 8601 datetime
    source_device: str = ""
    metadata: dict | None = None


class HealthSyncRequest(Schema):
    """Batch health data upload from mobile app."""

    source: str  # "healthkit" or "health_connect"
    observations: list[HealthObservationItem]


class HealthSyncResponse(Schema):
    """Response for health data sync."""

    received: int
    processed: int
    skipped: int
    errors: list[str]


def _ingest_single_observation(obs, index, patient, source, service):
    """Validate and ingest a single health observation.

    Returns:
        (True, None) on success
        (False, error_message) on validation/ingest failure
    """
    if obs.concept_id not in VALID_CONCEPT_IDS:
        return False, f"[{index}] Invalid concept_id: {obs.concept_id}"

    if obs.value_numeric is None and not obs.value_text:
        return False, f"[{index}] Missing value (numeric or text required)"

    try:
        observed_at = datetime.fromisoformat(obs.observed_at)
    except (ValueError, TypeError):
        return False, f"[{index}] Invalid observed_at: {obs.observed_at}"

    try:
        service.ingest_observation(
            patient=patient,
            concept_id=obs.concept_id,
            value_numeric=obs.value_numeric,
            value_text=obs.value_text,
            observed_at=observed_at,
            source=source,
            source_device=obs.source_device,
            quality="verified",
            metadata=obs.metadata or {},
            skip_processing=True,
        )
        return True, None
    except IntegrityError:
        return False, None  # Duplicate, skip silently
    except Exception as exc:
        return False, f"[{index}] Ingest error: {str(exc)[:100]}"


def _get_authenticated_patient(request):
    """Extract and validate the authenticated patient from the session."""
    session = request.session
    patient_id = session.get("patient_id")
    if not session.get("authenticated") or not patient_id:
        raise HttpError(401, "Authentication required")

    from apps.patients.models import Patient

    try:
        return Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist as exc:
        raise HttpError(404, "Patient not found") from exc


@router.post("/sync/", response=HealthSyncResponse)
def sync_health_data(request, data: HealthSyncRequest):
    """Batch ingest health data from HealthKit or Health Connect.

    Max 500 observations per request. Client paginates larger batches.
    Duplicate observations are silently skipped (unique constraint).
    Invalid concept_ids are skipped with an error message.
    Processing is deferred to avoid blocking the sync response.
    """
    patient = _get_authenticated_patient(request)

    if data.source not in ("healthkit", "health_connect"):
        raise HttpError(400, "Source must be 'healthkit' or 'health_connect'")

    if len(data.observations) > 500:
        raise HttpError(400, "Max 500 observations per request")

    if not data.observations:
        return HealthSyncResponse(received=0, processed=0, skipped=0, errors=[])

    from apps.clinical.services import ClinicalDataService

    processed = 0
    skipped = 0
    errors = []

    for i, obs in enumerate(data.observations):
        success, error = _ingest_single_observation(obs, i, patient, data.source, ClinicalDataService)
        if success:
            processed += 1
        else:
            skipped += 1
            if error:
                errors.append(error)

    # Trigger batch processing after all observations ingested
    if processed > 0:
        _queue_batch_processing(patient, processed)

    logger.info(
        "Health sync completed",
        extra={
            "patient_id": str(patient.id),
            "source": data.source,
            "received": len(data.observations),
            "processed": processed,
            "skipped": skipped,
        },
    )

    return HealthSyncResponse(
        received=len(data.observations),
        processed=processed,
        skipped=skipped,
        errors=errors[:10],
    )


def _queue_batch_processing(patient, processed):
    """Queue async batch processing for a patient after health sync."""
    try:
        from apps.clinical.tasks import process_patient_batch as process_batch_task

        process_batch_task.delay(str(patient.id))
    except Exception:
        logger.exception(
            "Failed to queue batch processing",
            extra={"patient_id": str(patient.id), "processed": processed},
        )
