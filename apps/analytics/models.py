"""Analytics app - Metrics and reporting."""

from django.db import models


class DailyMetrics(models.Model):
    """Aggregated daily metrics."""
    date = models.DateField(unique=True, db_index=True)

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

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_daily_metrics"
        verbose_name_plural = "Daily metrics"
        ordering = ["-date"]
