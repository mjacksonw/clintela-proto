"""Tests for analytics Celery tasks."""

import uuid as _uuid
from datetime import date, timedelta

from django.test import TestCase

from apps.analytics.models import DailyMetrics
from apps.analytics.tasks import compute_daily_metrics
from apps.patients.models import Hospital


def _code():
    return f"H-{_uuid.uuid4().hex[:8]}"


def _lc():
    return f"LC-{_uuid.uuid4().hex[:8]}"


class ComputeDailyMetricsTaskTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_task_default_yesterday(self):
        compute_daily_metrics()
        yesterday = date.today() - timedelta(days=1)
        assert DailyMetrics.objects.filter(date=yesterday).exists()

    def test_task_specific_date(self):
        compute_daily_metrics(date_str="2026-03-15")
        assert DailyMetrics.objects.filter(date=date(2026, 3, 15)).exists()

    def test_task_idempotent(self):
        compute_daily_metrics(date_str="2026-03-10")
        compute_daily_metrics(date_str="2026-03-10")
        assert DailyMetrics.objects.filter(date=date(2026, 3, 10), hospital__isnull=True).count() == 1
