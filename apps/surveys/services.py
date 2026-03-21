"""Business logic for the surveys app."""

import logging
from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.surveys.instruments import registry
from apps.surveys.models import (
    SurveyAnswer,
    SurveyAssignment,
    SurveyInstance,
    SurveyInstrument,
)
from apps.surveys.scoring import ScoringEngine

logger = logging.getLogger(__name__)


class SurveyService:
    """Service for survey assignment, completion, and chat integration."""

    @staticmethod
    @transaction.atomic
    def create_assignment(
        patient,
        instrument_code: str,
        schedule_type: str,
        assigned_by=None,
        pathway=None,
        start_date: date | None = None,
        end_date: date | None = None,
        escalation_config: dict | None = None,
    ) -> SurveyAssignment:
        """Create a survey assignment for a patient."""
        instrument = SurveyInstrument.objects.get(code=instrument_code, is_active=True)

        # Use instrument defaults for escalation if not provided
        if escalation_config is None:
            inst_cls = registry.get(instrument_code)
            escalation_config = inst_cls().get_escalation_defaults() if inst_cls else {}

        assignment = SurveyAssignment.objects.create(
            patient=patient,
            instrument=instrument,
            pathway=pathway,
            assigned_by=assigned_by,
            schedule_type=schedule_type,
            start_date=start_date or date.today(),
            end_date=end_date,
            escalation_config=escalation_config,
        )

        # Create first instance immediately if daily/weekly
        if schedule_type in ("daily", "weekly", "one_time"):
            SurveyService.create_instance_for_assignment(assignment)

        return assignment

    @staticmethod
    def create_instance_for_assignment(assignment: SurveyAssignment) -> SurveyInstance | None:
        """Create a new survey instance for an assignment if one doesn't exist.

        Uses try/except IntegrityError to handle concurrent creation attempts
        safely — the DB constraint uq_surveys_instance_one_active prevents
        duplicates even under concurrent load.
        """
        from django.db import IntegrityError

        # Quick check — avoids unnecessary work in the common case
        active = SurveyInstance.objects.filter(
            patient=assignment.patient,
            instrument=assignment.instrument,
            status__in=["pending", "available", "in_progress"],
        ).exists()

        if active:
            return None

        now = timezone.now()
        today = now.date()

        if assignment.schedule_type == "daily":
            window_start = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now.hour < 6:
                window_start -= timedelta(days=1)
            window_end = window_start + timedelta(days=1)
        elif assignment.schedule_type == "weekly":
            # Monday 6am to Sunday midnight
            days_since_monday = today.weekday()
            monday = today - timedelta(days=days_since_monday)
            window_start = datetime.combine(monday, datetime.min.time().replace(hour=6))
            window_start = timezone.make_aware(window_start)
            window_end = window_start + timedelta(days=7)
        elif assignment.schedule_type == "monthly":
            window_start = now.replace(day=1, hour=6, minute=0, second=0, microsecond=0)
            if now.month == 12:
                window_end = window_start.replace(year=now.year + 1, month=1)
            else:
                window_end = window_start.replace(month=now.month + 1)
        else:
            window_start = now
            window_end = now + timedelta(days=7)  # Default 7-day window

        try:
            return SurveyInstance.objects.create(
                assignment=assignment,
                patient=assignment.patient,
                instrument=assignment.instrument,
                status="available",
                due_date=today,
                window_start=window_start,
                window_end=window_end,
            )
        except IntegrityError:
            # Concurrent creation — another process already created the instance
            logger.info(
                "Instance already exists for %s/%s (concurrent creation)",
                assignment.patient_id,
                assignment.instrument.code,
            )
            return None

    @staticmethod
    def start_instance(instance: SurveyInstance) -> SurveyInstance:
        """Mark an instance as in-progress."""
        instance.status = "in_progress"
        instance.started_at = timezone.now()
        instance.save(update_fields=["status", "started_at"])
        return instance

    @staticmethod
    def save_answers(instance: SurveyInstance, answers: dict) -> list[SurveyAnswer]:
        """Save or update answers for a survey instance."""
        saved = []
        questions = {q.code: q for q in instance.instrument.questions.all()}

        for code, value in answers.items():
            question = questions.get(code)
            if question is None:
                continue

            answer, _created = SurveyAnswer.objects.update_or_create(
                instance=instance,
                question=question,
                defaults={
                    "value": value,
                    "raw_value": str(value),
                },
            )
            saved.append(answer)

        return saved

    @staticmethod
    @transaction.atomic
    def complete_instance(instance: SurveyInstance) -> SurveyInstance:
        """Complete a survey instance: score, check escalation, inject chat message."""
        instance.status = "completed"
        instance.completed_at = timezone.now()

        # Score the instance
        try:
            result = ScoringEngine.score_instance(instance)
            if result:
                instance.total_score = result.total_score
                instance.domain_scores = result.domain_scores
                instance.raw_scores = result.raw_scores

                # Check escalation
                if ScoringEngine.check_escalation(instance, result):
                    instance.escalation_triggered = True
                    SurveyService._create_escalation(instance, result)
            else:
                instance.scoring_error = True
        except Exception:  # noqa: S110  # nosec B110
            logger.exception("Scoring failed for instance %s", instance.id)
            instance.scoring_error = True

        instance.save()

        # Inject chat system message
        SurveyService._inject_completion_message(instance)

        # Check for score change alert
        SurveyService._check_score_change_alert(instance)

        return instance

    @staticmethod
    def _create_escalation(instance: SurveyInstance, result):
        """Create an escalation from a survey scoring result."""
        try:
            from apps.agents.services import EscalationService

            conversation = None
            try:
                from apps.agents.services import ConversationService

                conversation = ConversationService.get_or_create_conversation(instance.patient)
            except Exception:  # noqa: S110  # nosec B110
                pass

            escalation = EscalationService.create_escalation(
                patient=instance.patient,
                conversation=conversation,
                reason=result.escalation_reason,
                severity=result.escalation_severity,
                conversation_summary=f"Survey {instance.instrument.name} completed with score {result.total_score}",
            )
            instance.escalation = escalation

            from apps.notifications.services import NotificationService

            NotificationService.create_escalation_notification(escalation)
        except Exception:  # noqa: S110  # nosec B110
            logger.exception("Failed to create escalation for instance %s", instance.id)

    @staticmethod
    def _inject_completion_message(instance: SurveyInstance):
        """Inject a system message into the patient's chat conversation."""
        try:
            from apps.agents.models import AgentMessage
            from apps.agents.services import ConversationService

            conversation = ConversationService.get_or_create_conversation(instance.patient)

            if instance.scoring_error:
                content = (
                    f"You completed the {instance.instrument.name}. "
                    "Your responses have been saved. Your care team will review your answers shortly."
                )
                metadata = {
                    "type": "survey_completed",
                    "survey_instance_id": str(instance.id),
                    "instrument_code": instance.instrument.code,
                    "instrument_name": instance.instrument.name,
                    "scoring_error": True,
                }
            else:
                max_score = SurveyService._get_max_score(instance.instrument.code)
                score_text = f"Score: {instance.total_score}"
                if max_score:
                    score_text = f"Score: {instance.total_score}/{max_score}"

                # Get interpretation from scoring result
                interpretation = ""
                inst_cls = registry.get(instance.instrument.code)
                if inst_cls and instance.raw_scores:
                    try:
                        result = inst_cls().score(instance.raw_scores)
                        interpretation = result.interpretation
                    except Exception:  # noqa: S110  # nosec B110
                        pass

                content = f"You completed the {instance.instrument.name}. {score_text} — {interpretation}"
                metadata = {
                    "type": "survey_completed",
                    "survey_instance_id": str(instance.id),
                    "instrument_code": instance.instrument.code,
                    "instrument_name": instance.instrument.name,
                    "total_score": instance.total_score,
                    "max_score": max_score,
                }

            AgentMessage.objects.create(
                conversation=conversation,
                role="system",
                content=content,
                metadata=metadata,
            )
        except Exception:  # noqa: S110  # nosec B110
            logger.exception(
                "Failed to inject completion message for instance %s",
                instance.id,
            )

    @staticmethod
    def inject_missed_message(instance: SurveyInstance):
        """Inject a missed survey system message into chat."""
        try:
            from apps.agents.models import AgentMessage
            from apps.agents.services import ConversationService

            conversation = ConversationService.get_or_create_conversation(instance.patient)

            AgentMessage.objects.create(
                conversation=conversation,
                role="system",
                content=f"Your {instance.instrument.name} was not completed.",
                metadata={
                    "type": "survey_missed",
                    "survey_instance_id": str(instance.id),
                    "instrument_code": instance.instrument.code,
                    "instrument_name": instance.instrument.name,
                },
            )
        except Exception:  # noqa: S110  # nosec B110
            logger.exception(
                "Failed to inject missed message for instance %s",
                instance.id,
            )

    @staticmethod
    def _check_score_change_alert(instance: SurveyInstance):
        """Send WebSocket alert to clinician if score changed significantly."""
        if instance.scoring_error or instance.total_score is None:
            return

        inst_cls = registry.get(instance.instrument.code)
        if not inst_cls:
            return

        alert_config = inst_cls().get_change_alert_config()
        if not alert_config:
            return

        # Find previous completion
        previous = (
            SurveyInstance.objects.filter(
                patient=instance.patient,
                instrument=instance.instrument,
                status="completed",
                total_score__isnull=False,
            )
            .exclude(id=instance.id)
            .order_by("-completed_at")
            .first()
        )

        if previous is None:
            return  # First completion — no comparison

        delta = instance.total_score - previous.total_score
        min_delta = alert_config.get("min_delta", 0)
        direction = alert_config.get("direction", "increase")

        should_alert = False
        if (
            direction == "increase"
            and delta >= min_delta
            or direction == "decrease"
            and delta <= -min_delta
            or direction == "any"
            and abs(delta) >= min_delta
        ):
            should_alert = True

        if should_alert:
            SurveyService._send_clinician_alert(instance, delta, alert_config)

    @staticmethod
    def _send_clinician_alert(instance, delta, alert_config):
        """Send a WebSocket notification to the clinician dashboard."""
        try:
            from apps.notifications.services import NotificationService

            direction_text = "increased" if delta > 0 else "decreased"
            NotificationService.create_notification(
                patient=instance.patient,
                notification_type="alert",
                severity=alert_config.get("severity", "info"),
                title=f"{instance.instrument.name} score change",
                message=(
                    f"{instance.patient}'s {instance.instrument.name} score {direction_text} by {abs(delta):.0f} points"
                ),
            )
        except Exception:  # noqa: S110  # nosec B110
            logger.exception("Failed to send score change alert for instance %s", instance.id)

    @staticmethod
    def _get_max_score(instrument_code: str) -> float | None:
        """Get the max possible score for an instrument."""
        max_scores = {
            "phq_2": 6,
            "daily_symptom": 22,
            "kccq_12": 100,
            "saq_7": 100,
            "afeqt": 100,
            "promis_global": 60,
        }
        return max_scores.get(instrument_code)

    @staticmethod
    def auto_assign_from_pathway(patient_pathway):
        """Auto-assign surveys based on pathway defaults."""
        pathway = patient_pathway.pathway

        # Check for survey defaults in pathway metadata
        survey_defaults = pathway.metadata.get("survey_defaults", []) if hasattr(pathway, "metadata") else []

        if not survey_defaults:
            # Check PathwaySurveyDefault model if it exists
            return

        for config in survey_defaults:
            try:
                SurveyService.create_assignment(
                    patient=patient_pathway.patient,
                    instrument_code=config["instrument_code"],
                    schedule_type=config.get("schedule_type", "weekly"),
                    pathway=patient_pathway,
                    escalation_config=config.get("escalation_config"),
                )
                logger.info(
                    "Auto-assigned %s to patient %s via pathway %s",
                    config["instrument_code"],
                    patient_pathway.patient_id,
                    pathway.name,
                )
            except Exception:  # noqa: S110  # nosec B110
                logger.exception(
                    "Failed to auto-assign %s to patient %s",
                    config.get("instrument_code"),
                    patient_pathway.patient_id,
                )

    @staticmethod
    def get_available_surveys(patient) -> list[SurveyInstance]:
        """Get available/in-progress survey instances for a patient, sorted by estimated_minutes."""
        return list(
            SurveyInstance.objects.filter(
                patient=patient,
                status__in=["available", "in_progress"],
            )
            .select_related("instrument", "assignment")
            .order_by("instrument__estimated_minutes")
        )

    @staticmethod
    def get_next_survey_date(patient) -> date | None:
        """Get the next scheduled survey date for a patient."""
        next_instance = (
            SurveyInstance.objects.filter(
                patient=patient,
                status="pending",
            )
            .order_by("due_date")
            .values_list("due_date", flat=True)
            .first()
        )
        return next_instance

    @staticmethod
    def get_score_history(patient, limit: int = 5):
        """Get recent completed survey instances with scores."""
        return (
            SurveyInstance.objects.filter(
                patient=patient,
                status="completed",
                total_score__isnull=False,
            )
            .select_related("instrument")
            .order_by("-completed_at")[:limit]
        )
