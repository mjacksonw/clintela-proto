"""Celery tasks for analytics computation."""

import logging
from datetime import date, timedelta

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def compute_daily_metrics(self, date_str=None):
    """Compute and store DailyMetrics for a given date (default: yesterday).

    Runs nightly via Celery Beat. Can also be called manually.
    Idempotent: uses update_or_create so re-running is safe.
    """
    from apps.analytics.services import DailyMetricsService

    try:
        target_date = date.fromisoformat(date_str) if date_str else date.today() - timedelta(days=1)
        DailyMetricsService.compute_for_date(target_date)
        logger.info("compute_daily_metrics completed for %s", target_date)
    except Exception as exc:
        logger.exception("compute_daily_metrics failed for %s", date_str)
        raise self.retry(exc=exc) from exc
