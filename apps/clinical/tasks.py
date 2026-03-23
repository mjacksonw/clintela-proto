"""Celery tasks for clinical data processing."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="clinical.compute_all_snapshots")
def compute_all_snapshots():
    """Nightly snapshot recomputation for all active patients.

    Runs at 2:15 AM (offset from DailyMetrics at 2:07 AM).
    Catch-all that ensures all snapshots are current.
    """
    from apps.clinical.services import ClinicalDataService
    from apps.patients.models import Patient

    patients = Patient.objects.filter(is_active=True, clinical_observations__isnull=False).distinct()
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
