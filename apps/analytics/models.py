"""Analytics app - Metrics and reporting.

DailyMetrics stores pre-aggregated KPIs per hospital per day.
A row with hospital=NULL is the cross-hospital aggregate.
Populated nightly by the compute_daily_metrics Celery task.
"""

from django.db import models


class DailyMetrics(models.Model):
    """Aggregated daily metrics, per hospital."""

    date = models.DateField(db_index=True)
    hospital = models.ForeignKey(
        "patients.Hospital",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="NULL = cross-hospital aggregate row",
    )

    # Patient metrics
    total_patients = models.IntegerField(default=0)
    active_patients = models.IntegerField(default=0)
    new_patients = models.IntegerField(default=0)

    # Communication metrics
    messages_sent = models.IntegerField(default=0)
    messages_received = models.IntegerField(default=0)

    # Escalation metrics
    escalations = models.IntegerField(default=0)
    critical_escalations = models.IntegerField(default=0)

    # Response time metrics (in minutes)
    avg_response_time = models.FloatField(null=True, blank=True)

    # Readmission tracking
    discharges = models.IntegerField(default=0)
    readmissions = models.IntegerField(default=0)
    readmission_rate = models.FloatField(null=True, blank=True)

    # Engagement
    checkin_sent = models.IntegerField(default=0)
    checkin_completions = models.IntegerField(default=0)
    checkin_completion_rate = models.FloatField(null=True, blank=True)
    active_patients_with_messages = models.IntegerField(default=0)

    # Escalation detail
    pending_escalations = models.IntegerField(default=0)
    acknowledged_escalations = models.IntegerField(default=0)
    resolved_escalations = models.IntegerField(default=0)
    sla_breaches = models.IntegerField(default=0)
    avg_acknowledgment_time_minutes = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_daily_metrics"
        verbose_name_plural = "Daily metrics"
        ordering = ["-date"]
        unique_together = [("date", "hospital")]

    def __str__(self):
        hospital_name = self.hospital.name if self.hospital else "All"
        return f"Daily Metrics - {self.date} ({hospital_name})"
