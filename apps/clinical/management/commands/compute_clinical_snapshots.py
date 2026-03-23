"""Manually recompute clinical snapshots for all active patients."""

from django.core.management.base import BaseCommand

from apps.clinical.services import ClinicalDataService
from apps.patients.models import Patient


class Command(BaseCommand):
    help = "Recompute clinical snapshots for all active patients"

    def handle(self, *args, **options):
        patients = Patient.objects.filter(is_active=True)
        count = 0
        for patient in patients:
            if patient.clinical_observations.exists():
                ClinicalDataService.compute_snapshot(patient)
                count += 1
                self.stdout.write(f"  Recomputed snapshot for {patient}")

        self.stdout.write(self.style.SUCCESS(f"Done! Recomputed {count} snapshots."))
