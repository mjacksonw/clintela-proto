"""Patient services — recovery timeline and related logic."""

import logging
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# Warm messages keyed by day number — "help the patient be known"
WARM_MESSAGES = {
    1: _("Welcome home. Your recovery journey begins."),
    3: _("The first few days are the hardest. You're doing great."),
    7: _("One week! You're building great momentum."),
    14: _("Two weeks in. Every day counts."),
    30: _("One month! Look how far you've come."),
}


class RecoveryTimelineService:
    """Build a patient-facing recovery timeline from milestones, check-ins, and alerts."""

    @staticmethod
    def get_timeline(patient) -> list[dict]:
        """Build patient-facing timeline from milestones, check-ins, alerts, transitions.

        Returns list of timeline events sorted chronologically:
        [
            {"type": "milestone", "day": 1, "title": "...", "description": "...",
             "status": "completed"|"current"|"upcoming", "completed_at": datetime|None,
             "warm_message": "..."},
            {"type": "alert", "day": 5, "title": "...", "description": "...", "severity": "..."},
            ...
        ]
        """
        from apps.pathways.models import PatientMilestoneCheckin, PatientPathway

        # Find active pathway
        patient_pathway = (
            PatientPathway.objects.filter(patient=patient, status="active").select_related("pathway").first()
        )

        if not patient_pathway:
            return []

        # Get milestones for the pathway
        milestones = patient_pathway.pathway.milestones.filter(
            is_active=True,
        ).order_by("day")

        # Get check-ins for these milestones
        checkins = {
            ci.milestone_id: ci
            for ci in PatientMilestoneCheckin.objects.filter(
                patient=patient,
                milestone__in=milestones,
            ).select_related("milestone")
        }

        days_post_op = patient.days_post_op()
        timeline = []

        for milestone in milestones:
            checkin = checkins.get(milestone.id)
            is_completed = checkin is not None and checkin.completed_at is not None

            # Determine status
            if is_completed:
                status = "completed"
            elif days_post_op is not None and milestone.day <= days_post_op:
                status = "current"
            else:
                status = "upcoming"

            # Build warm message
            warm_message = WARM_MESSAGES.get(milestone.day, "")

            timeline.append(
                {
                    "type": "milestone",
                    "day": milestone.day,
                    "title": milestone.title,
                    "description": milestone.description,
                    "status": status,
                    "completed_at": checkin.completed_at if checkin else None,
                    "warm_message": str(warm_message) if warm_message else "",
                    "milestone_id": milestone.id,
                }
            )

        # Include clinical alerts from last 30 days (warm language)
        timeline.extend(RecoveryTimelineService._get_recent_alerts(patient, days_post_op))

        # Sort by day number
        timeline.sort(key=lambda e: e["day"])
        return timeline

    @staticmethod
    def _get_recent_alerts(patient, days_post_op) -> list[dict]:
        """Fetch recent clinical alerts and present them with warm language."""
        try:
            from apps.clinical.models import ClinicalAlert
        except ImportError:
            return []

        if days_post_op is None:
            return []

        cutoff = timezone.now() - timedelta(days=30)
        alerts = ClinicalAlert.objects.filter(
            patient=patient,
            created_at__gte=cutoff,
        ).order_by("created_at")[:10]

        result = []
        for alert in alerts:
            # Calculate approximate day for the alert
            alert_day = (alert.created_at.date() - patient.surgery_date).days if patient.surgery_date else 0

            # Use warm language for severity
            severity_labels = {
                "critical": str(_("Important update")),
                "warning": str(_("Something to watch")),
                "info": str(_("Good to know")),
            }
            warm_severity = severity_labels.get(alert.severity, str(_("Update")))

            result.append(
                {
                    "type": "alert",
                    "day": max(alert_day, 0),
                    "title": alert.title,
                    "description": alert.description,
                    "severity": alert.severity,
                    "warm_severity": warm_severity,
                    "created_at": alert.created_at,
                }
            )

        return result
