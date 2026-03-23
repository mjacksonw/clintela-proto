"""Seed realistic clinical observation data for demo scenarios.

Generates 30 days of time-series vital sign data with:
- Natural circadian variation (HR lower at night, BP dips)
- Post-surgical recovery curves (elevated vitals that normalize)
- Configurable anomaly scenarios (CHF decompensation, infection, etc.)
- Wearable source attribution (Apple Watch, Withings Scale)

Usage:
    python manage.py seed_clinical_data
    python manage.py seed_clinical_data --scenario all
    python manage.py seed_clinical_data --patient-id 1 --scenario chf

Production guard: refuses to run unless DEBUG=True.
"""

import math
import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.clinical.constants import (
    CONCEPT_BNP,
    CONCEPT_BODY_WEIGHT,
    CONCEPT_DAILY_STEPS,
    CONCEPT_DIASTOLIC_BP,
    CONCEPT_HEART_RATE,
    CONCEPT_SLEEP_DURATION,
    CONCEPT_SPO2,
    CONCEPT_SYSTOLIC_BP,
    CONCEPT_TEMPERATURE,
    CONCEPT_TROPONIN,
    SOURCE_EHR,
    SOURCE_WEARABLE,
)
from apps.clinical.services import ClinicalDataService
from apps.patients.models import Patient


class Command(BaseCommand):
    help = "Seed realistic clinical observation data for demo scenarios"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            type=str,
            default="all",
            choices=["all", "progressing", "chf", "infection", "declining"],
            help="Which anomaly scenario to generate (default: all)",
        )
        parser.add_argument(
            "--patient-id",
            type=int,
            help="Seed data for a specific patient ID only",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days of data to generate (default: 30)",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_clinical_data can only run with DEBUG=True (not in production)")

        scenario = options["scenario"]
        days = options["days"]
        patient_id = options.get("patient_id")

        if patient_id:
            patients = Patient.objects.filter(pk=patient_id)
            if not patients.exists():
                raise CommandError(f"Patient {patient_id} not found")
        else:
            patients = Patient.objects.filter(is_active=True)[:5]

        if not patients:
            raise CommandError("No patients found. Run create_test_patient first.")

        scenarios = {
            "progressing": self._scenario_progressing,
            "chf": self._scenario_chf_decompensation,
            "infection": self._scenario_infection,
            "declining": self._scenario_declining_activity,
        }

        scenario_list = list(scenarios.keys()) if scenario == "all" else [scenario]

        for i, patient in enumerate(patients):
            sc = scenario_list[i % len(scenario_list)]
            self.stdout.write(f"Seeding {sc} scenario for {patient}...")
            generator = scenarios[sc]
            count = generator(patient, days)
            self.stdout.write(f"  Created {count} observations")

            # Process once after all observations are inserted
            self.stdout.write("  Processing rules and computing snapshot...")
            ClinicalDataService.process_patient_batch(patient)

        self.stdout.write(self.style.SUCCESS(f"Done! Seeded clinical data for {len(patients)} patients."))

    def _scenario_progressing(self, patient, days):
        """Smooth recovery trajectory — vitals normalize over time."""
        count = 0
        base_time = timezone.now() - timedelta(days=days)

        for day in range(days):
            day_time = base_time + timedelta(days=day)
            progress = day / days  # 0.0 → 1.0 over recovery

            # HR: starts elevated (90-100), normalizes to 70-80
            for hour in [8, 12, 16, 20]:
                hr_base = 95 - (20 * progress)  # 95 → 75
                hr = hr_base + random.gauss(0, 3) + self._circadian_hr(hour)
                self._create_obs(patient, CONCEPT_HEART_RATE, hr, day_time, hour, "Apple Watch")
                count += 1

            # BP: starts elevated, normalizes
            for hour in [8, 20]:
                sbp_base = 145 - (20 * progress)
                dbp_base = 88 - (10 * progress)
                self._create_obs(
                    patient, CONCEPT_SYSTOLIC_BP, sbp_base + random.gauss(0, 5), day_time, hour, "Withings BPM"
                )
                self._create_obs(
                    patient, CONCEPT_DIASTOLIC_BP, dbp_base + random.gauss(0, 3), day_time, hour, "Withings BPM"
                )
                count += 2

            # Weight: stable (good sign)
            if day % 1 == 0:
                weight = 185 + random.gauss(0, 0.3)
                self._create_obs(patient, CONCEPT_BODY_WEIGHT, weight, day_time, 7, "Withings Scale")
                count += 1

            # SpO2: normalizes from 94 to 97
            for hour in [8, 14, 22]:
                spo2 = min(100, 94 + (3 * progress) + random.gauss(0, 0.5))
                self._create_obs(patient, CONCEPT_SPO2, spo2, day_time, hour, "Apple Watch")
                count += 1

            # Temp: normal
            temp = 98.4 + random.gauss(0, 0.3)
            self._create_obs(patient, CONCEPT_TEMPERATURE, temp, day_time, 8, "manual")
            count += 1

            # Steps: gradually increasing
            steps = max(0, int(500 + (4000 * progress) + random.gauss(0, 300)))
            self._create_obs(patient, CONCEPT_DAILY_STEPS, steps, day_time, 22, "Apple Watch")
            count += 1

        # Add some lab values (EHR-sourced)
        count += self._add_labs(patient, base_time, normal=True)
        return count

    def _scenario_chf_decompensation(self, patient, days):
        """Weight gain + HR elevation starting day 12 — CHF decompensation pattern."""
        count = 0
        base_time = timezone.now() - timedelta(days=days)

        for day in range(days):
            day_time = base_time + timedelta(days=day)
            # Day 0-11: normal recovery
            # Day 12+: weight starts creeping up, HR elevates
            is_decompensating = day >= 12
            decomp_day = max(0, day - 12)

            # HR: normal recovery then elevation
            for hour in [8, 12, 16, 20]:
                hr_base = 78 + (decomp_day * 1.5) if is_decompensating else 92 - (12 * (day / 12))
                hr = hr_base + random.gauss(0, 3) + self._circadian_hr(hour)
                self._create_obs(patient, CONCEPT_HEART_RATE, hr, day_time, hour, "Apple Watch")
                count += 1

            # Weight: stable then gaining
            weight = (
                185 + (decomp_day * 0.6) + random.gauss(0, 0.2) if is_decompensating else 185 + random.gauss(0, 0.3)
            )
            self._create_obs(patient, CONCEPT_BODY_WEIGHT, weight, day_time, 7, "Withings Scale")
            count += 1

            # BP
            for hour in [8, 20]:
                sbp = 130 + random.gauss(0, 5)
                dbp = 82 + random.gauss(0, 3)
                self._create_obs(patient, CONCEPT_SYSTOLIC_BP, sbp, day_time, hour, "Withings BPM")
                self._create_obs(patient, CONCEPT_DIASTOLIC_BP, dbp, day_time, hour, "Withings BPM")
                count += 2

            # SpO2: slight decline during decompensation
            for hour in [8, 14, 22]:
                if is_decompensating:
                    spo2 = max(91, 96 - (decomp_day * 0.3) + random.gauss(0, 0.5))
                else:
                    spo2 = 96 + random.gauss(0, 0.5)
                self._create_obs(patient, CONCEPT_SPO2, spo2, day_time, hour, "Apple Watch")
                count += 1

            # Steps: declining during decompensation
            if is_decompensating:
                steps = max(100, int(3000 - (decomp_day * 200) + random.gauss(0, 200)))
            else:
                steps = int(1500 + (1500 * (day / 12)) + random.gauss(0, 300))
            self._create_obs(patient, CONCEPT_DAILY_STEPS, steps, day_time, 22, "Apple Watch")
            count += 1

            # Temp: normal
            temp = 98.4 + random.gauss(0, 0.3)
            self._create_obs(patient, CONCEPT_TEMPERATURE, temp, day_time, 8, "manual")
            count += 1

        count += self._add_labs(patient, base_time, normal=False, bnp_elevated=True)
        return count

    def _scenario_infection(self, patient, days):
        """Temperature spike + HR elevation around day 5 — post-op infection."""
        count = 0
        base_time = timezone.now() - timedelta(days=days)

        for day in range(days):
            day_time = base_time + timedelta(days=day)

            # Day 4-8: infection window
            is_infected = 4 <= day <= 8
            infection_severity = max(0, min(1, (day - 4) / 2))  # Ramp up then down

            # HR: spikes during infection
            for hour in [8, 12, 16, 20]:
                hr_base = 88 + (25 * infection_severity) if is_infected else (82 - (day * 0.3) if day > 8 else 85)
                hr = hr_base + random.gauss(0, 3) + self._circadian_hr(hour)
                self._create_obs(patient, CONCEPT_HEART_RATE, hr, day_time, hour, "Apple Watch")
                count += 1

            # Temp: fever during infection
            if is_infected:
                temp = 99.5 + (2.5 * infection_severity) + random.gauss(0, 0.3)
            else:
                temp = 98.4 + random.gauss(0, 0.3)
            self._create_obs(patient, CONCEPT_TEMPERATURE, temp, day_time, 8, "manual")
            count += 1

            # Weight: stable
            weight = 170 + random.gauss(0, 0.3)
            self._create_obs(patient, CONCEPT_BODY_WEIGHT, weight, day_time, 7, "Withings Scale")
            count += 1

            # BP: slightly elevated during infection
            for hour in [8, 20]:
                sbp = 135 + (5 if is_infected else 0) + random.gauss(0, 5)
                dbp = 85 + random.gauss(0, 3)
                self._create_obs(patient, CONCEPT_SYSTOLIC_BP, sbp, day_time, hour, "Withings BPM")
                self._create_obs(patient, CONCEPT_DIASTOLIC_BP, dbp, day_time, hour, "Withings BPM")
                count += 2

            # SpO2: normal
            for hour in [8, 14, 22]:
                spo2 = 96 + random.gauss(0, 0.5)
                self._create_obs(patient, CONCEPT_SPO2, spo2, day_time, hour, "Apple Watch")
                count += 1

            # Steps: reduced during infection
            if is_infected:
                steps = max(100, int(800 + random.gauss(0, 200)))
            else:
                steps = int(2000 + (day * 100) + random.gauss(0, 300))
            self._create_obs(patient, CONCEPT_DAILY_STEPS, steps, day_time, 22, "Apple Watch")
            count += 1

        count += self._add_labs(patient, base_time, normal=True)
        return count

    def _scenario_declining_activity(self, patient, days):
        """Step count drops progressively — suggesting depression or pain."""
        count = 0
        base_time = timezone.now() - timedelta(days=days)

        for day in range(days):
            day_time = base_time + timedelta(days=day)
            progress = day / days

            # HR: mostly normal
            for hour in [8, 12, 16, 20]:
                hr = 76 + random.gauss(0, 3) + self._circadian_hr(hour)
                self._create_obs(patient, CONCEPT_HEART_RATE, hr, day_time, hour, "Apple Watch")
                count += 1

            # Weight: stable
            weight = 200 + random.gauss(0, 0.3)
            self._create_obs(patient, CONCEPT_BODY_WEIGHT, weight, day_time, 7, "Withings Scale")
            count += 1

            # BP: normal
            for hour in [8, 20]:
                self._create_obs(patient, CONCEPT_SYSTOLIC_BP, 128 + random.gauss(0, 5), day_time, hour, "Withings BPM")
                self._create_obs(patient, CONCEPT_DIASTOLIC_BP, 78 + random.gauss(0, 3), day_time, hour, "Withings BPM")
                count += 2

            # SpO2: normal
            for hour in [8, 14, 22]:
                spo2 = 97 + random.gauss(0, 0.5)
                self._create_obs(patient, CONCEPT_SPO2, spo2, day_time, hour, "Apple Watch")
                count += 1

            # Temp: normal
            temp = 98.4 + random.gauss(0, 0.3)
            self._create_obs(patient, CONCEPT_TEMPERATURE, temp, day_time, 8, "manual")
            count += 1

            # Steps: declining steadily over time
            base_steps = max(200, int(4000 * (1 - 0.7 * progress)))  # 4000 → 1200
            steps = max(100, int(base_steps + random.gauss(0, 200)))
            self._create_obs(patient, CONCEPT_DAILY_STEPS, steps, day_time, 22, "Apple Watch")
            count += 1

            # Sleep: getting worse
            sleep = max(3, 7.5 - (2 * progress) + random.gauss(0, 0.5))
            self._create_obs(patient, CONCEPT_SLEEP_DURATION, sleep, day_time, 7, "Apple Watch")
            count += 1

        count += self._add_labs(patient, base_time, normal=True)
        return count

    def _add_labs(self, patient, base_time, normal=True, bnp_elevated=False):
        """Add lab values as EHR-sourced observations."""
        count = 0
        # Labs at day 1, 7, 14
        for lab_day in [1, 7, 14]:
            lab_time = base_time + timedelta(days=lab_day)
            if lab_time > timezone.now():
                continue

            # BNP
            if bnp_elevated and lab_day >= 7:
                bnp = 250 + random.gauss(0, 30)
            else:
                bnp = 45 + random.gauss(0, 10) if normal else 120 + random.gauss(0, 20)
            self._create_obs(patient, CONCEPT_BNP, max(0, bnp), lab_time, 10, source_override=SOURCE_EHR)
            count += 1

            # Troponin
            trop = 0.02 + random.gauss(0, 0.005) if normal else 0.08 + random.gauss(0, 0.01)
            self._create_obs(patient, CONCEPT_TROPONIN, max(0, trop), lab_time, 10, source_override=SOURCE_EHR)
            count += 1

        return count

    def _create_obs(self, patient, concept_id, value, day_time, hour, device="", source_override=None):
        """Helper to create an observation with proper timestamp."""
        observed_at = day_time.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))
        source = source_override or SOURCE_WEARABLE
        ClinicalDataService.ingest_observation(
            patient=patient,
            concept_id=concept_id,
            value_numeric=round(value, 4),
            observed_at=observed_at,
            source=source,
            source_device=device if source != SOURCE_EHR else "",
            skip_processing=True,  # Bulk insert — process once at end
        )

    @staticmethod
    def _circadian_hr(hour):
        """Simulate circadian HR variation: lower at night, higher during activity."""
        # Simple sine wave: lowest at 3am, highest at 2pm
        return 5 * math.sin((hour - 3) * math.pi / 12)
