"""Celery tasks for clinical data processing."""

import logging

from celery import shared_task
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


# =============================================================================
# Proactive Patient Message Templates
# =============================================================================
# These messages pass the "known, not processed" test from philosophy.md.
# They use the language of the home, not the institution.
# {preferred_name} and {goal_reference} are filled at dispatch time.


def _get_proactive_message(category: str, preferred_name: str, goal_reference: str = "") -> str:
    """Get a warm, human message for a proactive patient outreach.

    These messages must:
    - Address the patient by name
    - Sound conversational, not clinical
    - Never alarm unnecessarily
    - Reference recovery goals when available
    - Feel like they come from someone who knows you
    """
    messages = {
        "missing_data": _(
            "Hey {preferred_name}, we haven't seen a reading from you in a couple "
            "of days. When you get a chance, could you check in? No rush — just helps "
            "us keep an eye on how you're doing.{goal_reference}"
        ),
        "weight_trend": _(
            "Hey {preferred_name}, your weight has been creeping up a bit over the "
            "last few days. Have you noticed any swelling in your ankles or feet? "
            "It might be nothing, but we'd rather check in than miss something."
            "{goal_reference}"
        ),
        "activity_decline": _(
            "We noticed you've been a bit less active lately, {preferred_name}. "
            "How are you feeling? Sometimes a slow day is just a slow day — but "
            "if something's bothering you, we're right here.{goal_reference}"
        ),
    }

    template = messages.get(category, messages["missing_data"])
    goal_suffix = f" {goal_reference}" if goal_reference else ""
    return template.format(preferred_name=preferred_name, goal_reference=goal_suffix)


@shared_task(name="clinical.send_proactive_patient_message")
def send_proactive_patient_message(patient_id: int, rule_name: str, message_category: str):
    """Send a proactive, warm message to a patient based on a clinical alert.

    This task is dispatched asynchronously so it doesn't block alert processing.
    The message goes through process_patient_message() so it appears naturally
    in the patient's chat conversation and benefits from preference injection.
    """
    from apps.agents.models import AgentConversation, AgentMessage
    from apps.patients.models import Patient

    try:
        patient = Patient.objects.select_related("user").get(pk=patient_id)
    except Patient.DoesNotExist:
        logger.warning("Proactive message: patient %s not found", patient_id)
        return

    # Build the preferred name
    preferred_name = patient.user.first_name or "there"
    try:
        if hasattr(patient, "preferences") and patient.preferences.preferred_name:
            preferred_name = patient.preferences.preferred_name
    except Exception:
        logger.debug("Could not load preferred_name for patient %s", patient_id)

    # Build goal reference if available
    goal_reference = ""
    try:
        if hasattr(patient, "preferences") and patient.preferences.recovery_goals:
            goals = patient.preferences.recovery_goals.strip()
            if goals:
                goal_reference = _(
                    " We want to make sure nothing slows down your recovery so you can get back to what matters to you."
                )
    except Exception:
        logger.debug("Could not load recovery_goals for patient %s", patient_id)

    message_text = _get_proactive_message(message_category, preferred_name, goal_reference)

    # Create/get active conversation and add the proactive message
    conversation = (
        AgentConversation.objects.filter(
            patient=patient,
            status="active",
        )
        .order_by("-created_at")
        .first()
    )

    if not conversation:
        conversation = AgentConversation.objects.create(
            patient=patient,
            agent_type="care_coordinator",
            status="active",
        )

    AgentMessage.objects.create(
        conversation=conversation,
        role="assistant",
        agent_type="care_coordinator",
        content=message_text,
        metadata={"proactive_rule": rule_name, "proactive_category": message_category},
    )

    logger.info(
        "Sent proactive %s message to patient %s (rule: %s)",
        message_category,
        patient_id,
        rule_name,
    )


@shared_task(name="clinical.process_patient_batch")
def process_patient_batch(patient_id: str):
    """Process clinical data after a batch health sync.

    Runs rules engine + snapshot recomputation for a patient
    after bulk observations are ingested from HealthKit / Health Connect.
    Called asynchronously so the sync endpoint responds quickly.
    """
    from apps.clinical.services import ClinicalDataService
    from apps.patients.models import Patient

    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        logger.warning("Batch processing: patient %s not found", patient_id)
        return

    try:
        ClinicalDataService.process_patient_batch(patient)
        logger.info("Batch processing complete for patient %s", patient_id)
    except Exception:
        logger.exception("Batch processing failed for patient %s", patient_id)


@shared_task(name="clinical.compute_all_snapshots")
def compute_all_snapshots():
    """Nightly snapshot recomputation for all active patients.

    Runs at 2:15 AM (offset from DailyMetrics at 2:07 AM).
    Catch-all that ensures all snapshots are current.
    """
    from apps.clinical.services import ClinicalDataService
    from apps.patients.models import Patient

    patients = Patient.objects.filter(is_active=True, clinical_observations__isnull=False).distinct().iterator()
    count = 0
    for patient in patients:
        try:
            ClinicalDataService.compute_snapshot(patient)
            count += 1
        except Exception:
            logger.exception("Snapshot recomputation failed for patient %s", patient.pk)

    logger.info("Recomputed %d clinical snapshots", count)
    return count


@shared_task(name="clinical.check_missing_data")
def check_missing_data():
    """Periodic missing data rule checks (every 6 hours).

    Runs missing data rules for patients with clinical observations
    to detect when wearable data stops flowing.
    """
    from apps.clinical.models import ClinicalAlert
    from apps.clinical.rules import RULE_REGISTRY
    from apps.clinical.services import ClinicalDataService
    from apps.patients.models import Patient

    missing_rules = {k: v for k, v in RULE_REGISTRY.items() if k.startswith("missing_")}
    if not missing_rules:
        return 0

    patients = Patient.objects.filter(is_active=True, clinical_observations__isnull=False).distinct()
    alerts_created = 0

    for patient in patients:
        for rule_name, rule_func in missing_rules.items():
            try:
                results = rule_func(patient)
                for result in results:
                    existing = ClinicalAlert.objects.filter(
                        patient=patient, rule_name=result.rule_name, status="active"
                    ).exists()
                    if not existing:
                        ClinicalDataService._create_or_update_alert(patient, result)
                        alerts_created += 1
            except Exception:
                logger.exception("Missing data rule '%s' failed for patient %s", rule_name, patient.pk)

    logger.info("Missing data check: %d new alerts", alerts_created)
    return alerts_created
