"""Clinical data service — ingest, snapshot, trend, triage.

Data flow:
  ingest_observation(skip_processing=False)
    │
    ├── 1. Save observation (own transaction)
    │
    └── 2. transaction.on_commit() (if not skip_processing)
         └── transaction.atomic()
              ├── check_all_rules() → ClinicalAlert creation
              ├── update_triage_color()
              └── compute_snapshot()
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.clinical.constants import (
    ALERT_STATUS_ACTIVE,
    CHART_VITALS,
    CONCEPT_NAMES,
    CONCEPT_UNITS,
    NORMAL_RANGES,
    SEVERITY_ORANGE,
    SEVERITY_RED,
    SEVERITY_TO_TRIAGE,
    SPARKLINE_VITALS,
    TRAJECTORY_CONCERNING,
    TRAJECTORY_DETERIORATING,
    TRAJECTORY_IMPROVING,
    TRAJECTORY_STABLE,
    VALID_CONCEPT_IDS,
)
from apps.clinical.models import ClinicalAlert, ClinicalObservation, PatientClinicalSnapshot

logger = logging.getLogger(__name__)


class ClinicalDataService:
    """Service for clinical data operations."""

    @staticmethod
    def ingest_observation(
        patient,
        concept_id: int,
        value_numeric=None,
        value_text: str = "",
        observed_at=None,
        source: str = "wearable",
        source_device: str = "",
        quality: str = "verified",
        metadata: dict | None = None,
        skip_processing: bool = False,
    ) -> ClinicalObservation:
        """Store a clinical observation and optionally trigger processing.

        Args:
            skip_processing: If True, skip rules check and snapshot recompute.
                Used by seed command for bulk ingestion performance.
        """
        if concept_id not in VALID_CONCEPT_IDS:
            raise ValueError(f"Invalid concept_id: {concept_id}. Valid IDs: {sorted(VALID_CONCEPT_IDS)}")

        concept_name = CONCEPT_NAMES[concept_id]
        unit = CONCEPT_UNITS[concept_id]

        if value_numeric is not None:
            value_numeric = Decimal(str(value_numeric))

        obs = ClinicalObservation.objects.create(
            patient=patient,
            concept_id=concept_id,
            concept_name=concept_name,
            value_numeric=value_numeric,
            value_text=value_text,
            unit=unit,
            observed_at=observed_at or timezone.now(),
            source=source,
            source_device=source_device,
            quality=quality,
            metadata=metadata or {},
        )

        if not skip_processing and getattr(settings, "ENABLE_CLINICAL_DATA", False):
            transaction.on_commit(lambda: ClinicalDataService._process_observation(patient))

        return obs

    @staticmethod
    def _process_observation(patient):
        """Post-commit processing: rules check + triage + snapshot.

        Wrapped in a single atomic block so partial failures
        roll back post-processing, not the observation.
        """
        try:
            with transaction.atomic():
                from apps.clinical.rules import check_all_rules

                results = check_all_rules(patient)
                for result in results:
                    ClinicalDataService._create_or_update_alert(patient, result)
                ClinicalDataService.update_triage_color(patient)
                ClinicalDataService.compute_snapshot(patient)
        except Exception:
            logger.exception("Clinical processing failed for patient %s", patient.pk)

    @staticmethod
    def _create_or_update_alert(patient, rule_result):
        """Create a new alert or update existing active alert (deduplication).

        Handles concurrent creation race via IntegrityError catch
        (UniqueConstraint on patient+rule_name WHERE active).
        """
        from django.db import IntegrityError

        existing = ClinicalAlert.objects.filter(
            patient=patient,
            rule_name=rule_result.rule_name,
            status=ALERT_STATUS_ACTIVE,
        ).first()

        if existing:
            existing.trigger_data = rule_result.trigger_data
            existing.save(update_fields=["trigger_data"])
            return existing

        try:
            alert = ClinicalAlert.objects.create(
                patient=patient,
                alert_type=rule_result.alert_type,
                severity=rule_result.severity,
                rule_name=rule_result.rule_name,
                title=rule_result.title,
                description=rule_result.description,
                rule_rationale=rule_result.rule_rationale,
                trigger_data=rule_result.trigger_data,
            )
        except IntegrityError:
            # Concurrent creation — another process created the alert first
            logger.info("Concurrent alert creation for %s/%s — updating existing", patient.pk, rule_result.rule_name)
            existing = ClinicalAlert.objects.filter(
                patient=patient, rule_name=rule_result.rule_name, status=ALERT_STATUS_ACTIVE
            ).first()
            if existing:
                existing.trigger_data = rule_result.trigger_data
                existing.save(update_fields=["trigger_data"])
            return existing

        # Escalation for RED/ORANGE alerts
        if rule_result.severity in (SEVERITY_RED, SEVERITY_ORANGE):
            ClinicalDataService._create_escalation(alert)

        # Proactive patient messaging for patient-facing rules
        ClinicalDataService._maybe_notify_patient(alert)

        return alert

    @staticmethod
    def _create_escalation(alert):
        """Create an escalation from a clinical alert."""
        try:
            from apps.agents.models import Escalation

            severity_map = {
                SEVERITY_RED: "critical",
                SEVERITY_ORANGE: "urgent",
            }
            escalation = Escalation.objects.create(
                patient=alert.patient,
                severity=severity_map.get(alert.severity, "routine"),
                escalation_type="clinical",
                reason=alert.description,
                patient_context={"alert_id": str(alert.id), "rule_name": alert.rule_name},
            )
            alert.escalation = escalation
            alert.save(update_fields=["escalation"])
        except Exception:
            logger.exception("Failed to create escalation for alert %s", alert.id)

    @staticmethod
    def update_triage_color(patient):
        """Update Patient.status based on active clinical alerts.

        Maps highest-severity active alert → triage color.
        If no active alerts, resets to green.
        """
        from apps.patients.models import Patient

        active_alerts = ClinicalAlert.objects.filter(
            patient=patient,
            status=ALERT_STATUS_ACTIVE,
        )

        # Determine worst severity
        new_status = "green"
        severity_order = [SEVERITY_RED, SEVERITY_ORANGE, "yellow", "info"]
        for severity in severity_order:
            if active_alerts.filter(severity=severity).exists():
                new_status = SEVERITY_TO_TRIAGE.get(severity, "green")
                break

        Patient.objects.filter(pk=patient.pk).update(status=new_status)
        patient.status = new_status

    @staticmethod
    def compute_snapshot(patient) -> PatientClinicalSnapshot:
        """Recompute the patient's clinical snapshot.

        Efficient: uses aggregation queries, not N+1.
        """
        vital_signs = ClinicalDataService.get_latest_vitals(patient)
        trajectory = ClinicalDataService._compute_trajectory(patient)
        active_count = ClinicalAlert.objects.filter(patient=patient, status=ALERT_STATUS_ACTIVE).count()
        risk_score = ClinicalDataService._compute_risk_score(patient, trajectory, active_count)
        data_completeness = ClinicalDataService._compute_data_completeness(patient)

        snapshot, _ = PatientClinicalSnapshot.objects.update_or_create(
            patient=patient,
            defaults={
                "vital_signs": vital_signs,
                "risk_score": risk_score,
                "trajectory": trajectory,
                "active_alerts_count": active_count,
                "data_completeness": data_completeness,
            },
        )
        return snapshot

    @staticmethod
    def get_latest_vitals(patient) -> dict:
        """Get the latest observation for each chart vital.

        Returns dict of concept_name → {value, at, unit, concept_id}.
        """
        result = {}
        for concept_id in CHART_VITALS:
            obs = (
                ClinicalObservation.objects.filter(
                    patient=patient,
                    concept_id=concept_id,
                    value_numeric__isnull=False,
                )
                .order_by("-observed_at")
                .values("value_numeric", "observed_at", "unit")
                .first()
            )
            if obs:
                name = CONCEPT_NAMES[concept_id]
                result[name] = {
                    "value": float(obs["value_numeric"]),
                    "at": obs["observed_at"].isoformat(),
                    "unit": obs["unit"],
                    "concept_id": concept_id,
                }
        return result

    @staticmethod
    def get_trend_data(patient, concept_id: int, days: int = 30) -> list[dict]:
        """Get time-series data for charting.

        Returns list of {value, at} dicts ordered chronologically.
        """
        since = timezone.now() - timedelta(days=days)
        return list(
            ClinicalObservation.objects.filter(
                patient=patient,
                concept_id=concept_id,
                observed_at__gte=since,
                value_numeric__isnull=False,
            )
            .order_by("observed_at")
            .values("value_numeric", "observed_at")
        )

    @staticmethod
    def get_patient_alerts(patient, status=None, limit=20) -> list:
        """Get alerts for a patient, optionally filtered by status."""
        qs = ClinicalAlert.objects.filter(patient=patient)
        if status:
            qs = qs.filter(status=status)
        return list(qs.order_by("-created_at")[:limit])

    @staticmethod
    def _compute_trajectory(patient) -> str:
        """Compute patient trajectory from vital trends.

        Precedence (worst wins):
        1. Deteriorating — any vital trending away from normal
        2. Concerning — no deterioration but any vital outside normal
        3. Improving — at least one vital trending toward normal
        4. Stable — all within normal and flat
        """
        from apps.clinical.rules import _compute_slope, _get_observations_in_window

        worst = TRAJECTORY_STABLE
        any_improving = False

        for concept_id, (low, high) in NORMAL_RANGES.items():
            observations = _get_observations_in_window(patient, concept_id, days=7)
            if len(observations) < 2:
                continue

            current_value = float(observations[-1][0])
            slope = _compute_slope(observations)
            if slope is None:
                continue

            in_range = low <= current_value <= high
            midpoint = (low + high) / 2

            if not in_range:
                # Outside normal range
                if current_value > high and slope > 0:
                    return TRAJECTORY_DETERIORATING
                if current_value < low and slope < 0:
                    return TRAJECTORY_DETERIORATING
                # Outside range but stable or improving
                if worst != TRAJECTORY_DETERIORATING:
                    worst = TRAJECTORY_CONCERNING
            else:
                # In range — check if moving toward midpoint
                if current_value > midpoint and slope < 0 or current_value < midpoint and slope > 0:
                    any_improving = True

        if worst == TRAJECTORY_STABLE and any_improving:
            return TRAJECTORY_IMPROVING
        return worst

    @staticmethod
    def _compute_risk_score(patient, trajectory: str, active_alerts_count: int) -> Decimal:
        """Compute composite risk score (0-100).

        Formula:
          +20 per RED alert, +10 per ORANGE, +5 per YELLOW
          +15 if deteriorating, +10 if concerning
          +10 if data_completeness < 0.5
        """
        score = 0
        alerts = ClinicalAlert.objects.filter(patient=patient, status=ALERT_STATUS_ACTIVE)
        score += alerts.filter(severity=SEVERITY_RED).count() * 20
        score += alerts.filter(severity=SEVERITY_ORANGE).count() * 10
        score += alerts.filter(severity="yellow").count() * 5

        if trajectory == TRAJECTORY_DETERIORATING:
            score += 15
        elif trajectory == TRAJECTORY_CONCERNING:
            score += 10

        completeness = ClinicalDataService._compute_data_completeness(patient)
        if completeness < Decimal("0.5"):
            score += 10

        return min(Decimal(score), Decimal(100))

    @staticmethod
    def _compute_data_completeness(patient) -> Decimal:
        """Compute how much data we have vs. expected.

        For each sparkline vital, check if we have at least one
        reading in the past 24 hours.
        """
        if not SPARKLINE_VITALS:
            return Decimal("0")

        since = timezone.now() - timedelta(hours=24)
        vitals_with_data = (
            ClinicalObservation.objects.filter(
                patient=patient,
                concept_id__in=SPARKLINE_VITALS,
                observed_at__gte=since,
            )
            .values("concept_id")
            .distinct()
            .count()
        )
        return Decimal(str(round(vitals_with_data / len(SPARKLINE_VITALS), 2)))

    # =========================================================================
    # Proactive Patient Messaging
    # =========================================================================

    # Rules that should trigger a warm, human message to the patient.
    # Each maps to a message template that passes the "known, not processed" test.
    PATIENT_FACING_RULES = {
        "missing_weight": "missing_data",
        "missing_hr": "missing_data",
        "weight_gain_3day": "weight_trend",
        "steps_declining_7day": "activity_decline",
    }

    @staticmethod
    def _maybe_notify_patient(alert):
        """Send a proactive message to the patient if this alert is patient-facing.

        Philosophy alignment: These messages must feel like they come from someone
        who knows the patient. Reference their name, goals, and situation.
        Never sound like a system notification.

        Dedup: Max 1 message per rule_name per patient per 24 hours.
        """
        if alert.rule_name not in ClinicalDataService.PATIENT_FACING_RULES:
            return

        # Dedup check: has this rule already messaged this patient in the last 24h?
        from apps.agents.models import AgentMessage

        since = timezone.now() - timedelta(hours=24)
        already_sent = AgentMessage.objects.filter(
            conversation__patient=alert.patient,
            metadata__proactive_rule=alert.rule_name,
            created_at__gte=since,
        ).exists()

        if already_sent:
            logger.debug(
                "Skipping proactive message for %s/%s — already sent within 24h",
                alert.patient.pk,
                alert.rule_name,
            )
            return

        # Check quiet hours — respect patient's preferred contact time
        try:
            now = timezone.localtime()
            hour = now.hour
            # Respect quiet hours: no proactive messages between 9pm and 8am
            if hour >= 21 or hour < 8:
                logger.debug(
                    "Deferring proactive message for %s — quiet hours (%d:00)",
                    alert.patient.pk,
                    hour,
                )
                return
        except Exception:
            logger.debug("Quiet hours check failed for patient %s, proceeding", alert.patient.pk)

        # Dispatch asynchronously via Celery
        from apps.clinical.tasks import send_proactive_patient_message

        message_category = ClinicalDataService.PATIENT_FACING_RULES[alert.rule_name]
        try:
            send_proactive_patient_message.delay(
                patient_id=alert.patient.pk,
                rule_name=alert.rule_name,
                message_category=message_category,
            )
        except Exception:
            logger.exception(
                "Failed to dispatch proactive message for patient %s, rule %s",
                alert.patient.pk,
                alert.rule_name,
            )

    @staticmethod
    def process_patient_batch(patient):
        """Run all rules and compute snapshot for a patient.

        Used after bulk ingestion (seed command) — call once per patient
        after all observations are inserted with skip_processing=True.
        Wrapped in transaction.atomic() for consistency.
        """
        from apps.clinical.rules import check_all_rules

        with transaction.atomic():
            results = check_all_rules(patient)
            for result in results:
                ClinicalDataService._create_or_update_alert(patient, result)
            ClinicalDataService.update_triage_color(patient)
            ClinicalDataService.compute_snapshot(patient)
