"""DailyMetrics computation service.

Computes and stores aggregated metrics for a given date.
Called nightly by Celery Beat and manually via management command.
"""

import logging
from datetime import date

from django.db.models import F, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class DailyMetricsService:
    @staticmethod
    def compute_for_date(target_date: date):
        """Compute all metrics for target_date and upsert into DailyMetrics.

        Creates one row per hospital + one NULL-hospital aggregate row.
        """
        from apps.agents.models import AgentMessage, Escalation
        from apps.analytics.models import DailyMetrics
        from apps.checkins.models import CheckinSession
        from apps.patients.models import Hospital, Patient, PatientStatusTransition

        hospitals = list(Hospital.objects.filter(is_active=True))
        # None = aggregate row
        hospital_list = [None] + hospitals

        for hospital in hospital_list:
            hospital_id = hospital.id if hospital else None
            hospital_filter = {"hospital_id": hospital_id} if hospital_id else {}
            patient_hospital_filter = {"patient__hospital_id": hospital_id} if hospital_id else {}
            conv_hospital_filter = {"conversation__patient__hospital_id": hospital_id} if hospital_id else {}

            # Patient counts
            patient_qs = Patient.objects.filter(is_active=True, **hospital_filter)
            total = patient_qs.count()
            new = Patient.objects.filter(created_at__date=target_date, **hospital_filter).count()

            # Messages
            msg_base = AgentMessage.objects.filter(created_at__date=target_date, **conv_hospital_filter)
            messages_sent = msg_base.filter(role="assistant").count()
            messages_received = msg_base.filter(role="user").count()

            # Active patients with messages
            active_with_msgs = msg_base.filter(role="user").values("conversation__patient_id").distinct().count()

            # Readmissions
            transition_base = PatientStatusTransition.objects.filter(
                created_at__date=target_date, **patient_hospital_filter
            )
            discharges = transition_base.filter(to_status="discharged").count()
            readmissions = transition_base.filter(to_status="readmitted").count()
            readmission_rate = round((readmissions / discharges) * 100, 1) if discharges > 0 else None

            # Escalations
            esc_base = Escalation.objects.filter(created_at__date=target_date, **patient_hospital_filter)
            escalations_count = esc_base.count()
            critical = esc_base.filter(severity="critical").count()

            # Escalation status on target_date
            pending = Escalation.objects.filter(
                status="pending", created_at__date__lte=target_date, **patient_hospital_filter
            ).count()
            acknowledged = esc_base.filter(acknowledged_at__date=target_date).count()
            resolved = esc_base.filter(resolved_at__date=target_date).count()

            # SLA breaches
            sla_breaches = (
                Escalation.objects.filter(
                    created_at__date=target_date,
                    response_deadline__isnull=False,
                    **patient_hospital_filter,
                )
                .filter(
                    Q(acknowledged_at__isnull=True, response_deadline__lt=timezone.now())
                    | Q(acknowledged_at__gt=F("response_deadline"))
                )
                .count()
            )

            # Avg acknowledgment time
            acked = Escalation.objects.filter(
                acknowledged_at__date=target_date,
                acknowledged_at__isnull=False,
                **patient_hospital_filter,
            )
            avg_ack_minutes = None
            if acked.exists():
                times = [(e.acknowledged_at - e.created_at).total_seconds() / 60 for e in acked]
                avg_ack_minutes = round(sum(times) / len(times), 1) if times else None

            # Avg response time (same as avg_ack for now)
            avg_response = avg_ack_minutes

            # Check-ins
            checkin_base = CheckinSession.objects.filter(date=target_date, **patient_hospital_filter)
            checkin_sent = checkin_base.count()
            checkin_done = checkin_base.filter(status="completed").count()
            checkin_rate = round((checkin_done / checkin_sent) * 100, 1) if checkin_sent > 0 else None

            DailyMetrics.objects.update_or_create(
                date=target_date,
                hospital=hospital,
                defaults={
                    "total_patients": total,
                    "active_patients": total,
                    "new_patients": new,
                    "messages_sent": messages_sent,
                    "messages_received": messages_received,
                    "escalations": escalations_count,
                    "critical_escalations": critical,
                    "avg_response_time": avg_response,
                    "discharges": discharges,
                    "readmissions": readmissions,
                    "readmission_rate": readmission_rate,
                    "checkin_sent": checkin_sent,
                    "checkin_completions": checkin_done,
                    "checkin_completion_rate": checkin_rate,
                    "active_patients_with_messages": active_with_msgs,
                    "pending_escalations": pending,
                    "acknowledged_escalations": acknowledged,
                    "resolved_escalations": resolved,
                    "sla_breaches": sla_breaches,
                    "avg_acknowledgment_time_minutes": avg_ack_minutes,
                },
            )

        logger.info("Computed DailyMetrics for %s (%d hospitals + aggregate)", target_date, len(hospitals))
