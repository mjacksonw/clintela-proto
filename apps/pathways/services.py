"""Pathway services — milestone celebrations and completion logic."""

import logging

from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class MilestoneCompletionService:
    """Handle milestone completion events, including celebrations."""

    @staticmethod
    def celebrate(patient, milestone, checkin):
        """Fire celebration when a milestone check-in is completed.

        Creates a celebration notification and returns the message.
        Idempotent: won't double-celebrate the same milestone.
        """
        from apps.notifications.models import Notification

        # Idempotency check: don't celebrate the same milestone twice
        already_celebrated = Notification.objects.filter(
            patient=patient,
            notification_type="celebration",
            title__contains=f"Day {milestone.day}",
        ).exists()

        if already_celebrated:
            logger.debug(
                "Already celebrated milestone day %d for patient %s",
                milestone.day,
                patient.id,
            )
            return None

        # Build personalized celebration message
        message = MilestoneCompletionService._build_celebration_message(patient, milestone)

        notification = Notification.objects.create(
            patient=patient,
            notification_type="celebration",
            severity="info",
            title=str(_("Day %(day)d milestone reached!") % {"day": milestone.day}),
            message=message,
        )

        logger.info(
            "Celebration created for patient %s — milestone day %d",
            patient.id,
            milestone.day,
        )
        return notification

    @staticmethod
    def _build_celebration_message(patient, milestone):
        """Build a warm, personalized celebration message."""
        # Try to reference recovery goals if available
        recovery_goals = ""
        try:
            if hasattr(patient, "preferences") and patient.preferences.recovery_goals:
                recovery_goals = patient.preferences.recovery_goals
        except Exception:
            logger.debug("Could not load recovery_goals for celebration")

        base_messages = {
            1: _("You made it through your first day home. That takes courage."),
            3: _("Three days in — the hardest part is often behind you now. Keep going."),
            7: _("A whole week! Your body is healing and you're taking great care of yourself."),
            14: _("Two weeks of recovery. You should be proud of how far you've come."),
            30: _("One month! This is a major milestone. You've shown real dedication to your recovery."),
        }

        message = str(
            base_messages.get(
                milestone.day,
                _("You've completed another milestone. Keep up the great work!"),
            )
        )

        if recovery_goals:
            message += " " + str(_("Every step brings you closer to what matters most to you."))

        return message
