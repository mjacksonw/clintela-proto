"""Celery tasks for the surveys app."""

import logging

from celery import shared_task
from django.utils import timezone

from apps.surveys.models import SurveyAssignment, SurveyInstance
from apps.surveys.services import SurveyService

logger = logging.getLogger(__name__)


@shared_task
def create_survey_instances():
    """Create new survey instances for active assignments.

    Runs daily. Checks all active assignments and creates instances where needed.
    """
    assignments = SurveyAssignment.objects.filter(
        is_active=True,
        start_date__lte=timezone.now().date(),
    ).select_related("patient", "instrument")

    created = 0
    for assignment in assignments:
        # Skip if end_date has passed
        if assignment.end_date and assignment.end_date < timezone.now().date():
            continue

        try:
            instance = SurveyService.create_instance_for_assignment(assignment)
            if instance:
                created += 1
        except Exception:
            logger.exception(
                "Failed to create instance for assignment %s",
                assignment.id,
            )

    logger.info("Created %d survey instances", created)


@shared_task
def expire_survey_instances():
    """Expire and mark missed survey instances.

    Runs every 30 minutes.
    - Available instances past window_end → missed
    - In-progress instances past window_end + 2 hours → missed (grace period)
    """
    now = timezone.now()
    grace_period = now - timezone.timedelta(hours=2)

    # Atomic update: mark available past window → missed
    available_ids = list(
        SurveyInstance.objects.filter(
            status="available",
            window_end__lt=now,
        ).values_list("id", flat=True)
    )
    available_count = SurveyInstance.objects.filter(
        id__in=available_ids,
        status="available",  # Re-check status atomically
    ).update(status="missed")

    # Atomic update: mark in-progress past window + grace → missed
    in_progress_ids = list(
        SurveyInstance.objects.filter(
            status="in_progress",
            window_end__lt=grace_period,
        ).values_list("id", flat=True)
    )
    in_progress_count = SurveyInstance.objects.filter(
        id__in=in_progress_ids,
        status="in_progress",  # Re-check status atomically
    ).update(status="missed")

    # Send notifications for missed instances
    missed_instances = SurveyInstance.objects.filter(
        id__in=available_ids + in_progress_ids,
        status="missed",
    ).select_related("patient", "instrument", "assignment")

    for instance in missed_instances:
        SurveyService.inject_missed_message(instance)
        _check_consecutive_misses(instance)

    total = available_count + in_progress_count
    if total:
        logger.info("Marked %d survey instances as missed", total)


def _check_consecutive_misses(instance: SurveyInstance):
    """Create escalation if patient has 3+ consecutive misses for an instrument."""
    consecutive = SurveyInstance.objects.filter(
        patient=instance.patient,
        instrument=instance.instrument,
        status="missed",
    ).order_by("-created_at")[:3]

    if len(list(consecutive)) >= 3:
        # Check that all 3 most recent are misses (no completed in between)
        recent = SurveyInstance.objects.filter(
            patient=instance.patient,
            instrument=instance.instrument,
            status__in=["completed", "missed"],
        ).order_by("-created_at")[:3]
        if all(i.status == "missed" for i in recent):
            try:
                from apps.agents.services import EscalationService

                EscalationService.create_escalation(
                    patient=instance.patient,
                    conversation=None,
                    reason=(f"Patient has missed 3 consecutive {instance.instrument.name} surveys"),
                    severity="routine",
                )
            except Exception:
                logger.exception(
                    "Failed to create consecutive miss escalation for %s",
                    instance.patient_id,
                )
