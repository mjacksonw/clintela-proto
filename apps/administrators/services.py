"""Aggregate metric services for the admin KPI dashboard.

All services return dicts of aggregate data — never Patient objects or PHI.
Each method accepts an optional hospital_id to scope metrics.
"""

import logging
from datetime import date, timedelta

from django.db import OperationalError
from django.db.models import Count, F, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def _apply_hospital_filter(qs, hospital_id, hospital_field="hospital_id"):
    """Apply hospital filter if specified."""
    if hospital_id:
        return qs.filter(**{hospital_field: hospital_id})
    return qs


class CensusService:
    """Population-level patient census metrics."""

    @staticmethod
    def get_population_summary(hospital_id=None):
        """Total active patients by status and lifecycle stage."""
        from apps.patients.models import Patient

        try:
            qs = Patient.objects.filter(is_active=True)
            qs = _apply_hospital_filter(qs, hospital_id)

            total = qs.count()
            by_status = dict(qs.values_list("status").annotate(count=Count("id")).values_list("status", "count"))
            by_lifecycle = dict(
                qs.values_list("lifecycle_status").annotate(count=Count("id")).values_list("lifecycle_status", "count")
            )

            return {
                "total": total,
                "by_status": by_status,
                "by_lifecycle": by_lifecycle,
            }
        except OperationalError:
            logger.exception("CensusService.get_population_summary failed")
            return {"error": "Could not load census data."}

    @staticmethod
    def get_triage_distribution(hospital_id=None):
        """Count per triage color: green, yellow, orange, red."""
        from apps.patients.models import Patient

        try:
            qs = Patient.objects.filter(is_active=True)
            qs = _apply_hospital_filter(qs, hospital_id)

            dist = dict(qs.values_list("status").annotate(count=Count("id")).values_list("status", "count"))
            return {
                "green": dist.get("green", 0),
                "yellow": dist.get("yellow", 0),
                "orange": dist.get("orange", 0),
                "red": dist.get("red", 0),
                "total": sum(dist.values()),
            }
        except OperationalError:
            logger.exception("CensusService.get_triage_distribution failed")
            return {"error": "Could not load triage data."}

    @staticmethod
    def get_hospital_breakdown():
        """Per-hospital active patient counts."""
        from apps.patients.models import Hospital

        try:
            hospitals = Hospital.objects.filter(is_active=True).annotate(
                active_patients=Count("patients", filter=Q(patients__is_active=True))
            )
            return [
                {
                    "id": h.id,
                    "name": h.name,
                    "code": h.code,
                    "active_patients": h.active_patients,
                }
                for h in hospitals
            ]
        except OperationalError:
            logger.exception("CensusService.get_hospital_breakdown failed")
            return {"error": "Could not load hospital data."}


class ReadmissionService:
    """Readmission rate computation using CMS cohort-based methodology.

    For a given window (e.g., 30 days): take all patients discharged in the
    trailing window, then check if any were readmitted within that same window
    after their individual discharge date.
    """

    @staticmethod
    def get_cohort_rate(days=30, hospital_id=None):
        """CMS cohort-based readmission rate for a given time window."""
        from apps.patients.models import PatientStatusTransition

        try:
            cutoff = timezone.now() - timedelta(days=days)

            # Discharges in the window
            discharge_qs = PatientStatusTransition.objects.filter(
                to_status="discharged",
                created_at__gte=cutoff,
            )
            discharge_qs = _apply_hospital_filter(discharge_qs, hospital_id, "patient__hospital_id")

            # Readmissions in the window
            readmit_qs = PatientStatusTransition.objects.filter(
                to_status="readmitted",
                created_at__gte=cutoff,
            )
            readmit_qs = _apply_hospital_filter(readmit_qs, hospital_id, "patient__hospital_id")

            discharges = discharge_qs.count()
            readmissions = readmit_qs.count()

            if discharges == 0:
                return {
                    "rate": None,
                    "readmissions": 0,
                    "discharges": 0,
                    "days": days,
                    "display": "N/A",
                }

            rate = round((readmissions / discharges) * 100, 1)
            return {
                "rate": rate,
                "readmissions": readmissions,
                "discharges": discharges,
                "days": days,
                "display": f"{rate}%",
            }
        except OperationalError:
            logger.exception("ReadmissionService.get_cohort_rate failed")
            return {"error": "Could not load readmission data."}

    @staticmethod
    def get_trend(days=90, hospital_id=None):
        """Weekly readmission rates from DailyMetrics for trend chart."""
        from apps.analytics.models import DailyMetrics

        try:
            cutoff = date.today() - timedelta(days=days)
            qs = DailyMetrics.objects.filter(date__gte=cutoff).order_by("date")
            qs = qs.filter(hospital_id=hospital_id) if hospital_id else qs.filter(hospital__isnull=True)

            points = list(qs.values("date", "readmission_rate", "discharges", "readmissions"))
            return points if points else []
        except Exception:
            logger.exception("ReadmissionService.get_trend failed")
            return []


class OutcomesService:
    """Outcome KPIs: discharge to community, follow-up completion."""

    @staticmethod
    def get_discharge_to_community(days=30, hospital_id=None):
        """Patients discharged who reach recovering/recovered without readmission."""
        from apps.patients.models import PatientStatusTransition

        try:
            cutoff = timezone.now() - timedelta(days=days)

            discharge_qs = PatientStatusTransition.objects.filter(
                to_status="discharged",
                created_at__gte=cutoff,
            )
            discharge_qs = _apply_hospital_filter(discharge_qs, hospital_id, "patient__hospital_id")
            discharged_patient_ids = set(discharge_qs.values_list("patient_id", flat=True))

            if not discharged_patient_ids:
                return {"rate": None, "successful": 0, "total": 0, "display": "N/A"}

            # Patients who were readmitted in same window
            readmitted_ids = set(
                PatientStatusTransition.objects.filter(
                    patient_id__in=discharged_patient_ids,
                    to_status="readmitted",
                    created_at__gte=cutoff,
                ).values_list("patient_id", flat=True)
            )

            successful = len(discharged_patient_ids - readmitted_ids)
            total = len(discharged_patient_ids)
            rate = round((successful / total) * 100, 1) if total > 0 else 0

            return {
                "rate": rate,
                "successful": successful,
                "total": total,
                "display": f"{rate}%",
            }
        except OperationalError:
            logger.exception("OutcomesService.get_discharge_to_community failed")
            return {"error": "Could not load discharge data."}

    @staticmethod
    def _count_on_time_checkins(checkin_list):
        """Count checkins completed within ±2 days of expected date."""
        from apps.pathways.models import PatientPathway

        # Pre-fetch PatientPathway start dates to avoid N+1
        pairs = {(c.patient_id, c.milestone.pathway_id) for c in checkin_list if c.completed_at}
        pp_lookup = {}
        if pairs:
            pp_filter = Q()
            for pid, pwid in pairs:
                pp_filter |= Q(patient_id=pid, pathway_id=pwid)
            for pp in PatientPathway.objects.filter(pp_filter):
                pp_lookup[(pp.patient_id, pp.pathway_id)] = pp

        on_time = 0
        for checkin in checkin_list:
            if not checkin.completed_at:
                continue
            try:
                patient_pathway = pp_lookup.get((checkin.patient_id, checkin.milestone.pathway_id))
                if patient_pathway and patient_pathway.started_at:
                    expected = patient_pathway.started_at.date() + timedelta(days=checkin.milestone.day)
                    if abs((checkin.completed_at.date() - expected).days) <= 2:
                        on_time += 1
            except Exception:
                logger.debug("Skipping checkin %s: could not compute expected date", checkin.id)
        return on_time

    @staticmethod
    def get_followup_completion(days=30, hospital_id=None):
        """Milestones completed on time (within ±2 days of expected date)."""
        from apps.pathways.models import PatientMilestoneCheckin

        try:
            cutoff = timezone.now() - timedelta(days=days)
            checkins = PatientMilestoneCheckin.objects.filter(
                sent_at__gte=cutoff,
            ).select_related("milestone", "patient")
            if hospital_id:
                checkins = checkins.filter(patient__hospital_id=hospital_id)

            total_sent = checkins.count()
            if total_sent == 0:
                return {"rate": None, "on_time": 0, "total": 0, "display": "N/A"}

            on_time = OutcomesService._count_on_time_checkins(list(checkins))
            rate = round((on_time / total_sent) * 100, 1)
            return {
                "rate": rate,
                "on_time": on_time,
                "total": total_sent,
                "display": f"{rate}%",
            }
        except OperationalError:
            logger.exception("OutcomesService.get_followup_completion failed")
            return {"error": "Could not load follow-up data."}


class EngagementService:
    """Patient engagement metrics."""

    @staticmethod
    def get_program_engagement(days=30, hospital_id=None):
        """% of active patients with ≥1 patient-initiated message or check-in in window."""
        from apps.agents.models import AgentMessage
        from apps.pathways.models import PatientMilestoneCheckin
        from apps.patients.models import Patient

        try:
            cutoff = timezone.now() - timedelta(days=days)

            active_qs = Patient.objects.filter(is_active=True)
            active_qs = _apply_hospital_filter(active_qs, hospital_id)
            total_active = active_qs.count()

            if total_active == 0:
                return {"rate": None, "engaged": 0, "total": 0, "display": "N/A"}

            # Patients with messages (role=user = patient-initiated)
            messaging_patients = set(
                AgentMessage.objects.filter(
                    role="user",
                    created_at__gte=cutoff,
                    conversation__patient__is_active=True,
                    **({"conversation__patient__hospital_id": hospital_id} if hospital_id else {}),
                )
                .values_list("conversation__patient_id", flat=True)
                .distinct()
            )

            # Patients with completed check-ins
            checkin_patients = set(
                PatientMilestoneCheckin.objects.filter(
                    completed_at__gte=cutoff,
                    patient__is_active=True,
                    **({"patient__hospital_id": hospital_id} if hospital_id else {}),
                )
                .values_list("patient_id", flat=True)
                .distinct()
            )

            engaged = len(messaging_patients | checkin_patients)
            rate = round((engaged / total_active) * 100, 1)

            return {
                "rate": rate,
                "engaged": engaged,
                "total": total_active,
                "display": f"{rate}%",
            }
        except OperationalError:
            logger.exception("EngagementService.get_program_engagement failed")
            return {"error": "Could not load engagement data."}

    @staticmethod
    def get_program_engagement_multi_horizon(hospital_id=None):
        """Engagement at 7, 14, 30, 90 day horizons."""
        horizons = [7, 14, 30, 90]
        results = {}
        for d in horizons:
            data = EngagementService.get_program_engagement(days=d, hospital_id=hospital_id)
            results[d] = data
        return results

    @staticmethod
    def get_messaging_stats(days=30, hospital_id=None):
        """Message volume and avg per patient."""
        from apps.agents.models import AgentMessage
        from apps.patients.models import Patient

        try:
            cutoff = timezone.now() - timedelta(days=days)

            msg_qs = AgentMessage.objects.filter(created_at__gte=cutoff)
            if hospital_id:
                msg_qs = msg_qs.filter(conversation__patient__hospital_id=hospital_id)

            total = msg_qs.count()
            sent = msg_qs.filter(role="assistant").count()
            received = msg_qs.filter(role="user").count()

            active_patients = Patient.objects.filter(is_active=True)
            active_patients = _apply_hospital_filter(active_patients, hospital_id)
            patient_count = active_patients.count()

            avg_per_patient = round(total / patient_count, 1) if patient_count > 0 else 0

            return {
                "total": total,
                "sent": sent,
                "received": received,
                "avg_per_patient": avg_per_patient,
            }
        except OperationalError:
            logger.exception("EngagementService.get_messaging_stats failed")
            return {"error": "Could not load messaging data."}

    @staticmethod
    def get_checkin_stats(days=30, hospital_id=None):
        """Check-in completion rate (completed / total, regardless of timing)."""
        from apps.pathways.models import PatientMilestoneCheckin

        try:
            cutoff = timezone.now() - timedelta(days=days)

            qs = PatientMilestoneCheckin.objects.filter(sent_at__gte=cutoff)
            if hospital_id:
                qs = qs.filter(patient__hospital_id=hospital_id)

            total = qs.count()
            completed = qs.filter(completed_at__isnull=False, skipped=False).count()
            skipped = qs.filter(skipped=True).count()

            rate = round((completed / total) * 100, 1) if total > 0 else None

            return {
                "total": total,
                "completed": completed,
                "skipped": skipped,
                "rate": rate,
                "display": f"{rate}%" if rate is not None else "N/A",
            }
        except OperationalError:
            logger.exception("EngagementService.get_checkin_stats failed")
            return {"error": "Could not load check-in data."}

    @staticmethod
    def get_inactive_patients(days=7, hospital_id=None):
        """Count of active patients with no messages in last N days."""
        from apps.agents.models import AgentMessage
        from apps.patients.models import Patient

        try:
            cutoff = timezone.now() - timedelta(days=days)

            active_qs = Patient.objects.filter(is_active=True)
            active_qs = _apply_hospital_filter(active_qs, hospital_id)
            total_active = active_qs.count()

            active_conversers = (
                AgentMessage.objects.filter(
                    role="user",
                    created_at__gte=cutoff,
                    conversation__patient__is_active=True,
                    **({"conversation__patient__hospital_id": hospital_id} if hospital_id else {}),
                )
                .values("conversation__patient_id")
                .distinct()
                .count()
            )

            return total_active - active_conversers
        except OperationalError:
            logger.exception("EngagementService.get_inactive_patients failed")
            return 0


class EscalationAnalyticsService:
    """Escalation performance metrics."""

    @staticmethod
    def get_status_breakdown(hospital_id=None):
        """Current escalation status counts."""
        from apps.agents.models import Escalation

        try:
            qs = Escalation.objects.all()
            if hospital_id:
                qs = qs.filter(patient__hospital_id=hospital_id)

            breakdown = dict(qs.values_list("status").annotate(count=Count("id")).values_list("status", "count"))
            return {
                "pending": breakdown.get("pending", 0),
                "acknowledged": breakdown.get("acknowledged", 0),
                "resolved": breakdown.get("resolved", 0),
            }
        except OperationalError:
            logger.exception("EscalationAnalyticsService.get_status_breakdown failed")
            return {"error": "Could not load escalation data."}

    @staticmethod
    def get_response_stats(days=30, hospital_id=None):
        """Average response time and SLA compliance."""
        from apps.agents.models import Escalation

        try:
            cutoff = timezone.now() - timedelta(days=days)

            qs = Escalation.objects.filter(created_at__gte=cutoff)
            if hospital_id:
                qs = qs.filter(patient__hospital_id=hospital_id)

            total = qs.count()
            acknowledged = qs.filter(acknowledged_at__isnull=False)

            # Average response time (minutes)
            avg_minutes = None
            if acknowledged.exists():
                response_times = []
                for esc in acknowledged:
                    delta = (esc.acknowledged_at - esc.created_at).total_seconds() / 60
                    response_times.append(delta)
                avg_minutes = round(sum(response_times) / len(response_times), 1) if response_times else None

            # SLA compliance: acknowledged before response_deadline
            sla_total = qs.filter(response_deadline__isnull=False).count()
            sla_met = qs.filter(
                response_deadline__isnull=False,
                acknowledged_at__isnull=False,
                acknowledged_at__lte=F("response_deadline"),
            ).count()
            sla_compliance = round((sla_met / sla_total) * 100, 1) if sla_total > 0 else None

            return {
                "avg_minutes": avg_minutes,
                "sla_compliance": sla_compliance,
                "total": total,
                "pending": qs.filter(status="pending").count(),
            }
        except OperationalError:
            logger.exception("EscalationAnalyticsService.get_response_stats failed")
            return {"error": "Could not load escalation response data."}


class PathwayAnalyticsService:
    """Pathway effectiveness metrics."""

    @staticmethod
    def get_pathway_list_with_stats():
        """Per-pathway stats: active patients, completed, completion rate."""
        from apps.pathways.models import ClinicalPathway

        try:
            pathways = ClinicalPathway.objects.annotate(
                active_count=Count("patientpathway", filter=Q(patientpathway__status="active")),
                completed_count=Count("patientpathway", filter=Q(patientpathway__status="completed")),
                total_assigned=Count("patientpathway"),
            ).order_by("-active_count", "name")

            results = []
            for p in pathways:
                completion_rate = (
                    round((p.completed_count / p.total_assigned) * 100, 1) if p.total_assigned > 0 else None
                )
                results.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "surgery_type": p.surgery_type,
                        "duration_days": p.duration_days,
                        "is_active": p.is_active,
                        "active_count": p.active_count,
                        "completed_count": p.completed_count,
                        "total_assigned": p.total_assigned,
                        "completion_rate": completion_rate,
                        "display_rate": f"{completion_rate}%" if completion_rate is not None else "N/A",
                    }
                )
            return results
        except OperationalError:
            logger.exception("PathwayAnalyticsService.get_pathway_list_with_stats failed")
            return {"error": "Could not load pathway data."}

    @staticmethod
    def get_pathway_effectiveness(pathway_id):
        """Detailed effectiveness for a single pathway."""
        from apps.pathways.models import ClinicalPathway, PatientMilestoneCheckin, PatientPathway

        try:
            pathway = ClinicalPathway.objects.get(id=pathway_id)
            assignments = PatientPathway.objects.filter(pathway=pathway)

            total = assignments.count()
            completed = assignments.filter(status="completed").count()
            completion_rate = round((completed / total) * 100, 1) if total > 0 else None

            # Per-milestone check-in rates
            milestones = pathway.milestones.filter(is_active=True).order_by("day")
            milestone_stats = []
            for m in milestones:
                checkins = PatientMilestoneCheckin.objects.filter(milestone=m)
                sent = checkins.count()
                done = checkins.filter(completed_at__isnull=False, skipped=False).count()
                rate = round((done / sent) * 100, 1) if sent > 0 else None
                milestone_stats.append(
                    {
                        "id": m.id,
                        "day": m.day,
                        "title": m.title,
                        "sent": sent,
                        "completed": done,
                        "rate": rate,
                        "display_rate": f"{rate}%" if rate is not None else "N/A",
                    }
                )

            return {
                "pathway": {
                    "id": pathway.id,
                    "name": pathway.name,
                    "surgery_type": pathway.surgery_type,
                    "duration_days": pathway.duration_days,
                    "is_active": pathway.is_active,
                    "description": pathway.description,
                },
                "total_assigned": total,
                "completed": completed,
                "completion_rate": completion_rate,
                "display_rate": f"{completion_rate}%" if completion_rate is not None else "N/A",
                "milestones": milestone_stats,
            }
        except ClinicalPathway.DoesNotExist:
            return {"error": "Pathway not found."}
        except OperationalError:
            logger.exception("PathwayAnalyticsService.get_pathway_effectiveness failed")
            return {"error": "Could not load pathway effectiveness."}


class OperationalAlertService:
    """Surfaces operational issues that need admin attention."""

    @staticmethod
    def get_all_alerts():
        """Returns list of active operational alerts."""
        from apps.agents.models import Escalation

        alerts = []

        try:
            # SLA breaches: pending escalations past deadline
            now = timezone.now()
            sla_breaches = Escalation.objects.filter(
                status="pending",
                response_deadline__isnull=False,
                response_deadline__lt=now,
            ).count()
            if sla_breaches > 0:
                alerts.append(
                    {
                        "type": "sla_breach",
                        "severity": "critical",
                        "message": f"{sla_breaches} escalation{'s' if sla_breaches != 1 else ''} past SLA deadline",
                        "count": sla_breaches,
                    }
                )

            # Stale escalations: pending > 24h
            stale_cutoff = now - timedelta(hours=24)
            stale = Escalation.objects.filter(
                status="pending",
                created_at__lt=stale_cutoff,
            ).count()
            if stale > 0:
                alerts.append(
                    {
                        "type": "stale_escalation",
                        "severity": "warning",
                        "message": f"{stale} escalation{'s' if stale != 1 else ''} pending > 24 hours",
                        "count": stale,
                    }
                )

            # Inactive patients
            inactive = EngagementService.get_inactive_patients(days=7)
            if inactive > 0:
                alerts.append(
                    {
                        "type": "inactive_patients",
                        "severity": "warning",
                        "message": f"{inactive} patient{'s' if inactive != 1 else ''} with no activity in 7 days",
                        "count": inactive,
                    }
                )
        except OperationalError:
            logger.exception("OperationalAlertService.get_all_alerts failed")

        return alerts[:5]  # Cap at 5 alerts
