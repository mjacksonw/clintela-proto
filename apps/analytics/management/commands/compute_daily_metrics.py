"""Management command to compute DailyMetrics.

Usage:
    python manage.py compute_daily_metrics                  # Yesterday
    python manage.py compute_daily_metrics --date 2026-03-20   # Specific date
    python manage.py compute_daily_metrics --backfill 90       # Last 90 days
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.analytics.services import DailyMetricsService


class Command(BaseCommand):
    help = "Compute DailyMetrics for a date or backfill a range."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, help="Specific date (YYYY-MM-DD)")
        parser.add_argument("--backfill", type=int, help="Backfill N days from today")

    def handle(self, *args, **options):
        if options["backfill"]:
            days = options["backfill"]
            self.stdout.write(f"Backfilling {days} days...")
            for i in range(days, 0, -1):
                target = date.today() - timedelta(days=i)
                DailyMetricsService.compute_for_date(target)
                self.stdout.write(f"  {target}")
            self.stdout.write(self.style.SUCCESS(f"Backfilled {days} days of metrics."))
        elif options["date"]:
            target = date.fromisoformat(options["date"])
            DailyMetricsService.compute_for_date(target)
            self.stdout.write(self.style.SUCCESS(f"Computed metrics for {target}."))
        else:
            target = date.today() - timedelta(days=1)
            DailyMetricsService.compute_for_date(target)
            self.stdout.write(self.style.SUCCESS(f"Computed metrics for {target} (yesterday)."))
