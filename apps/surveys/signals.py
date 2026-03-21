"""Signal handlers for the surveys app."""

import logging

logger = logging.getLogger(__name__)


def on_patient_pathway_created(sender, instance, created, **kwargs):
    """Auto-create survey assignments when a patient is assigned a pathway.

    Reads PathwaySurveyDefault records (or JSON config on the pathway) and
    creates SurveyAssignment records for the patient.
    """
    if not created:
        return

    from apps.surveys.services import SurveyService

    try:
        SurveyService.auto_assign_from_pathway(instance)
    except Exception:
        logger.exception(
            "Failed to auto-assign surveys for pathway %s, patient %s",
            instance.pathway_id,
            instance.patient_id,
        )
