"""Hand-crafted demo fixture data for surveys and DailyMetrics.

Every data point is written by hand to tell a compelling narrative.
Do NOT replace with programmatic generation — the realism is the point.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.analytics.models import DailyMetrics
from apps.patients.models import Hospital, Patient, PatientStatusTransition
from apps.surveys.models import SurveyAssignment, SurveyInstance, SurveyInstrument


class Command(BaseCommand):
    help = "Seed hand-crafted demo fixtures: survey scores, DailyMetrics, and Margaret Torres."

    def handle(self, *args, **options):
        hospital = Hospital.objects.filter(code="SJMC").first()
        if not hospital:
            self.stdout.write(self.style.ERROR("No hospital found. Run create_cardiology_service first."))
            return

        kccq = SurveyInstrument.objects.filter(code="kccq_12").first()
        if not kccq:
            self.stdout.write(self.style.ERROR("No KCCQ-12 instrument found. Run seed_instruments first."))
            return

        self._create_margaret_torres(hospital, kccq)
        self._create_survey_histories(hospital, kccq)
        self._create_discharge_transitions(hospital)
        self._create_daily_metrics(hospital)

        self.stdout.write(self.style.SUCCESS("\nDemo fixtures seeded successfully."))

    # -----------------------------------------------------------------------
    # Margaret Torres — the demo patient
    # -----------------------------------------------------------------------

    def _create_margaret_torres(self, hospital, kccq):
        """Create the demo patient with empty conversation and pending KCCQ-12."""
        self.stdout.write("Creating Margaret Torres (demo patient)...")

        user, _ = User.objects.get_or_create(
            username="margaret_torres",
            defaults={
                "first_name": "Margaret",
                "last_name": "Torres",
                "email": "margaret.torres@example.com",
                "role": "patient",
            },
        )

        today = date.today()
        patient, _ = Patient.objects.get_or_create(
            user=user,
            defaults={
                "hospital": hospital,
                "surgery_type": "CABG",
                "surgery_date": today - timedelta(days=8),
                "discharge_date": today - timedelta(days=5),
                "status": "yellow",
                "lifecycle_status": "recovering",
                "leaflet_code": "DEMO-MARGARET",
                "date_of_birth": date(1960, 3, 14),
            },
        )

        # One completed KCCQ-12 from 3 days ago (score: 58 — moderate limitation)
        assignment, _ = SurveyAssignment.objects.get_or_create(
            patient=patient,
            instrument=kccq,
            is_active=True,
            defaults={
                "schedule_type": "weekly",
                "start_date": today - timedelta(days=7),
            },
        )

        three_days_ago = today - timedelta(days=3)
        SurveyInstance.objects.get_or_create(
            assignment=assignment,
            patient=patient,
            instrument=kccq,
            status="completed",
            due_date=three_days_ago,
            defaults={
                "window_start": timezone.make_aware(
                    timezone.datetime.combine(three_days_ago, timezone.datetime.min.time())
                ),
                "window_end": timezone.make_aware(
                    timezone.datetime.combine(three_days_ago, timezone.datetime.max.time())
                ),
                "started_at": timezone.now() - timedelta(days=3, hours=2),
                "completed_at": timezone.now() - timedelta(days=3, hours=1, minutes=45),
                "total_score": 58.3,
                "domain_scores": {
                    "physical_limitation": 41.7,
                    "symptom_frequency": 58.3,
                    "symptom_burden": 62.5,
                    "social_limitation": 50.0,
                    "quality_of_life": 75.0,
                },
                "raw_scores": {
                    "pl_dressing": 3,
                    "pl_showering": 2,
                    "pl_walking": 2,
                    "sf_frequency": 3,
                    "sf_fatigue": 3,
                    "sf_shortness": 4,
                    "sb_frequency": 4,
                    "sb_bother": 3,
                    "sl_social": 3,
                    "sl_intimacy": 2,
                    "ql_satisfaction": 4,
                    "ql_discouraged": 4,
                },
            },
        )

        # One pending KCCQ-12 due today (for live demo)
        SurveyInstance.objects.get_or_create(
            assignment=assignment,
            patient=patient,
            instrument=kccq,
            status="available",
            due_date=today,
            defaults={
                "window_start": timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time())),
                "window_end": timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time())),
            },
        )

        self.stdout.write("  Margaret Torres: /patient/dashboard/ (leaflet: DEMO-MARGARET)")

    # -----------------------------------------------------------------------
    # Survey histories for key patients
    # -----------------------------------------------------------------------

    def _create_survey_histories(self, hospital, kccq):
        """Create KCCQ-12 score histories for named patients, telling different stories."""
        self.stdout.write("Creating survey histories...")

        today = date.today()
        patients_data = self._get_survey_narratives(today)

        for patient_name, scores in patients_data.items():
            first, last = patient_name.split(" ", 1)
            patient = Patient.objects.filter(user__first_name=first, user__last_name=last).first()
            if not patient:
                self.stdout.write(f"  Skipping {patient_name} (not found)")
                continue

            assignment, _ = SurveyAssignment.objects.get_or_create(
                patient=patient,
                instrument=kccq,
                is_active=True,
                defaults={
                    "schedule_type": "weekly",
                    "start_date": today - timedelta(days=30),
                },
            )

            for score_entry in scores:
                days_ago = score_entry["days_ago"]
                score_date = today - timedelta(days=days_ago)
                SurveyInstance.objects.get_or_create(
                    assignment=assignment,
                    patient=patient,
                    instrument=kccq,
                    status="completed",
                    due_date=score_date,
                    defaults={
                        "window_start": timezone.make_aware(
                            timezone.datetime.combine(score_date, timezone.datetime.min.time())
                        ),
                        "window_end": timezone.make_aware(
                            timezone.datetime.combine(score_date, timezone.datetime.max.time())
                        ),
                        "started_at": timezone.now() - timedelta(days=days_ago, hours=3),
                        "completed_at": timezone.now() - timedelta(days=days_ago, hours=2, minutes=45),
                        "total_score": score_entry["total"],
                        "domain_scores": score_entry["domains"],
                        "raw_scores": score_entry.get("raw", {}),
                    },
                )

            self.stdout.write(f"  {patient_name}: {len(scores)} KCCQ-12 scores")

    def _get_survey_narratives(self, today):
        """Hand-crafted survey score narratives for key patients.

        Each patient tells a different clinical story through their scores.
        KCCQ-12: 0-100, higher is better.
          0-24: Severe limitation
          25-49: Significant limitation
          50-74: Moderate limitation
          75-100: Good health status
        """
        return {
            # Robert Chen — Day 2 CABG, red status. Very early post-op.
            # Only one score: severely limited, expected this soon after surgery.
            "Robert Chen": [
                {
                    "days_ago": 1,
                    "total": 22.5,
                    "domains": {
                        "physical_limitation": 8.3,
                        "symptom_frequency": 25.0,
                        "symptom_burden": 25.0,
                        "social_limitation": 12.5,
                        "quality_of_life": 37.5,
                    },
                    "raw": {
                        "pl_dressing": 1,
                        "pl_showering": 1,
                        "pl_walking": 2,
                        "sf_frequency": 2,
                        "sf_fatigue": 2,
                        "sf_shortness": 2,
                        "sb_frequency": 2,
                        "sb_bother": 2,
                        "sl_social": 1,
                        "sl_intimacy": 1,
                        "ql_satisfaction": 2,
                        "ql_discouraged": 3,
                    },
                },
            ],
            # Linda Rodriguez — Day 8, yellow. Steady improvement story.
            # Three weekly scores showing gradual recovery.
            "Linda Rodriguez": [
                {
                    "days_ago": 7,
                    "total": 35.0,
                    "domains": {
                        "physical_limitation": 25.0,
                        "symptom_frequency": 33.3,
                        "symptom_burden": 37.5,
                        "social_limitation": 25.0,
                        "quality_of_life": 50.0,
                    },
                },
                {
                    "days_ago": 3,
                    "total": 47.5,
                    "domains": {
                        "physical_limitation": 33.3,
                        "symptom_frequency": 50.0,
                        "symptom_burden": 50.0,
                        "social_limitation": 37.5,
                        "quality_of_life": 62.5,
                    },
                },
            ],
            # Joseph Wilson — Day 25, green. The success story.
            # Four scores showing strong upward trajectory.
            "Joseph Wilson": [
                {
                    "days_ago": 24,
                    "total": 30.0,
                    "domains": {
                        "physical_limitation": 16.7,
                        "symptom_frequency": 33.3,
                        "symptom_burden": 25.0,
                        "social_limitation": 25.0,
                        "quality_of_life": 50.0,
                    },
                },
                {
                    "days_ago": 17,
                    "total": 48.3,
                    "domains": {
                        "physical_limitation": 33.3,
                        "symptom_frequency": 50.0,
                        "symptom_burden": 50.0,
                        "social_limitation": 37.5,
                        "quality_of_life": 62.5,
                    },
                },
                {
                    "days_ago": 10,
                    "total": 65.0,
                    "domains": {
                        "physical_limitation": 50.0,
                        "symptom_frequency": 66.7,
                        "symptom_burden": 68.8,
                        "social_limitation": 62.5,
                        "quality_of_life": 75.0,
                    },
                },
                {
                    "days_ago": 3,
                    "total": 79.2,
                    "domains": {
                        "physical_limitation": 66.7,
                        "symptom_frequency": 83.3,
                        "symptom_burden": 81.3,
                        "social_limitation": 75.0,
                        "quality_of_life": 87.5,
                    },
                },
            ],
            # Michael Thompson — Day 12, yellow. Plateau/concern story.
            # Three scores that improved then stalled.
            "Michael Thompson": [
                {
                    "days_ago": 11,
                    "total": 40.0,
                    "domains": {
                        "physical_limitation": 33.3,
                        "symptom_frequency": 41.7,
                        "symptom_burden": 37.5,
                        "social_limitation": 37.5,
                        "quality_of_life": 50.0,
                    },
                },
                {
                    "days_ago": 6,
                    "total": 50.8,
                    "domains": {
                        "physical_limitation": 41.7,
                        "symptom_frequency": 50.0,
                        "symptom_burden": 50.0,
                        "social_limitation": 50.0,
                        "quality_of_life": 62.5,
                    },
                },
                {
                    "days_ago": 1,
                    "total": 46.7,
                    "domains": {
                        "physical_limitation": 33.3,
                        "symptom_frequency": 50.0,
                        "symptom_burden": 43.8,
                        "social_limitation": 43.8,
                        "quality_of_life": 62.5,
                    },
                },
            ],
            # Patricia Williams — Day 5, orange. Early and struggling.
            # Two scores, both low. Need attention.
            "Patricia Williams": [
                {
                    "days_ago": 4,
                    "total": 27.5,
                    "domains": {
                        "physical_limitation": 16.7,
                        "symptom_frequency": 25.0,
                        "symptom_burden": 31.3,
                        "social_limitation": 18.8,
                        "quality_of_life": 43.8,
                    },
                },
                {
                    "days_ago": 1,
                    "total": 30.8,
                    "domains": {
                        "physical_limitation": 16.7,
                        "symptom_frequency": 33.3,
                        "symptom_burden": 31.3,
                        "social_limitation": 25.0,
                        "quality_of_life": 50.0,
                    },
                },
            ],
            # Charles Clark — Day 45, green. Fully recovered, great trajectory.
            # Five scores showing complete arc.
            "Charles Clark": [
                {
                    "days_ago": 42,
                    "total": 25.0,
                    "domains": {
                        "physical_limitation": 16.7,
                        "symptom_frequency": 25.0,
                        "symptom_burden": 25.0,
                        "social_limitation": 18.8,
                        "quality_of_life": 37.5,
                    },
                },
                {
                    "days_ago": 35,
                    "total": 42.5,
                    "domains": {
                        "physical_limitation": 33.3,
                        "symptom_frequency": 41.7,
                        "symptom_burden": 43.8,
                        "social_limitation": 37.5,
                        "quality_of_life": 56.3,
                    },
                },
                {
                    "days_ago": 28,
                    "total": 60.0,
                    "domains": {
                        "physical_limitation": 50.0,
                        "symptom_frequency": 58.3,
                        "symptom_burden": 62.5,
                        "social_limitation": 56.3,
                        "quality_of_life": 75.0,
                    },
                },
                {
                    "days_ago": 14,
                    "total": 77.5,
                    "domains": {
                        "physical_limitation": 66.7,
                        "symptom_frequency": 83.3,
                        "symptom_burden": 81.3,
                        "social_limitation": 68.8,
                        "quality_of_life": 87.5,
                    },
                },
                {
                    "days_ago": 3,
                    "total": 89.2,
                    "domains": {
                        "physical_limitation": 83.3,
                        "symptom_frequency": 91.7,
                        "symptom_burden": 93.8,
                        "social_limitation": 81.3,
                        "quality_of_life": 93.8,
                    },
                },
            ],
        }

    # -----------------------------------------------------------------------
    # Discharge/Readmission transitions for readmission rate hero card
    # -----------------------------------------------------------------------

    def _create_discharge_transitions(self, hospital):
        """Create discharge/readmission transitions across 120 days.

        The ReadmissionService.get_cohort_rate() queries PatientStatusTransition for
        to_status="discharged" and to_status="readmitted".

        Narrative arc — readmission rate DROPS as the program matures:
          120d window: ~11%  (early days, program just starting)
           90d window: ~8%   (improving, learning what works)
           60d window: ~6%   (engagement catching problems earlier)
           30d window: ~4%   (program is working well)
            7d window: 0%    (recent performance is excellent)

        We achieve this by creating "historical" patients who were admitted,
        treated, and discharged 60-120 days ago — with higher readmission rates
        in the earlier cohorts. These patients don't need conversations or detail;
        they just need User + Patient + transitions.
        """
        self.stdout.write("Creating discharge/readmission transitions...")

        today = date.today()

        # ---------------------------------------------------------------
        # Phase 1: Create historical patients (days 60-120)
        # These are patients who have already completed their recovery.
        # They exist only to populate the longitudinal readmission data.
        # ---------------------------------------------------------------

        # Hand-crafted historical cohorts: (discharge_days_ago, readmitted?)
        # Each entry creates one patient with discharge + optional readmission.
        historical_cohorts = [
            # Days 100-120: Early program — high readmission rate (~15%)
            # 8 discharges, 2 readmissions (one wound infection, one medication error)
            ("Helen", "Park", 73, "CABG", 118, True, "Surgical site infection requiring IV antibiotics"),
            ("George", "Foster", 81, "Aortic Valve Replacement", 115, False, None),
            ("Ruth", "Reed", 69, "CABG", 112, False, None),
            (
                "Frank",
                "Butler",
                77,
                "Mitral Valve Repair",
                110,
                True,
                "Medication non-compliance leading to fluid overload",
            ),
            ("Virginia", "Brooks", 65, "PCI with Stent", 108, False, None),
            ("Raymond", "Price", 72, "CABG", 105, False, None),
            ("Alice", "Howard", 68, "CABG", 102, False, None),
            ("Harold", "Ward", 75, "Aortic Valve Replacement", 100, False, None),
            # Days 80-99: Getting better — moderate readmission rate (~10%)
            # 7 discharges, 1 readmission
            ("Gloria", "Cox", 70, "CABG", 97, False, None),
            ("Eugene", "Barnes", 66, "PCI with Stent", 94, True, "Chest pain workup — ruled out MI, stent patent"),
            ("Shirley", "Long", 74, "CABG", 91, False, None),
            ("Carl", "Patterson", 63, "Mitral Valve Replacement", 88, False, None),
            ("Jean", "Hughes", 71, "CABG", 85, False, None),
            ("Walter", "Flores", 67, "Aortic Valve Replacement", 82, False, None),
            ("Martha", "Simmons", 76, "CABG", 80, False, None),
            # Days 60-79: Improving — lower readmission rate (~7%)
            # 8 discharges, 1 readmission
            ("Henry", "Russell", 64, "PCI with Stent", 78, False, None),
            ("Frances", "Griffin", 72, "CABG", 75, False, None),
            ("Roy", "Diaz", 69, "CABG", 73, True, "Atrial fibrillation with rapid ventricular response"),
            ("Evelyn", "Sanders", 66, "Mitral Valve Repair", 70, False, None),
            ("Albert", "Perry", 78, "CABG", 68, False, None),
            ("Marie", "Powell", 61, "PCI with Stent", 65, False, None),
            ("Clarence", "Jenkins", 73, "Aortic Valve Replacement", 63, False, None),
            ("Doris", "Bell", 68, "CABG", 60, False, None),
            # Days 45-59: Program hitting stride — low readmission rate (~5%)
            # 6 discharges, 0 readmissions in this window
            ("Ernest", "Coleman", 70, "CABG", 58, False, None),
            ("Phyllis", "Morgan", 65, "PCI with Stent", 55, False, None),
            ("Clifford", "Wood", 74, "CABG", 52, False, None),
            ("Norma", "Hayes", 67, "Mitral Valve Replacement", 50, False, None),
            ("Gordon", "Bryant", 71, "CABG", 48, False, None),
            ("Edna", "Alexander", 63, "Aortic Valve Replacement", 46, False, None),
        ]

        historical_created = 0
        readmit_count = 0
        transitions = []

        for first, last, age, surgery, days_ago, readmitted, readmit_reason in historical_cohorts:
            username = f"hist_{first.lower()}_{last.lower()}"

            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": "patient",
                },
            )

            surgery_date = today - timedelta(days=days_ago + 5)  # surgery 5 days before discharge
            discharge_date = today - timedelta(days=days_ago)

            patient, created = Patient.objects.get_or_create(
                user=user,
                defaults={
                    "hospital": hospital,
                    "surgery_type": surgery,
                    "surgery_date": surgery_date,
                    "discharge_date": discharge_date,
                    "status": "green",
                    "lifecycle_status": "readmitted" if readmitted else "recovered",
                    "date_of_birth": date(today.year - age, 1, 15),
                    "leaflet_code": f"HIST-{first[0]}{last[0]}-{days_ago}",
                },
            )

            if not created:
                continue

            historical_created += 1

            # Discharge transition
            discharge_dt = timezone.make_aware(
                timezone.datetime.combine(discharge_date, timezone.datetime.min.time())
            ) + timedelta(hours=14)

            transitions.append(
                PatientStatusTransition(
                    patient=patient,
                    from_status="post_op",
                    to_status="discharged",
                    triggered_by="clinical_team",
                    reason="Post-operative recovery on track, discharge criteria met",
                    created_at=discharge_dt,
                )
            )

            # Readmission transition (if applicable)
            if readmitted and readmit_reason:
                readmit_date = discharge_date + timedelta(days=7)
                readmit_dt = timezone.make_aware(
                    timezone.datetime.combine(readmit_date, timezone.datetime.min.time())
                ) + timedelta(hours=9)

                transitions.append(
                    PatientStatusTransition(
                        patient=patient,
                        from_status="recovering",
                        to_status="readmitted",
                        triggered_by="emergency_department",
                        reason=readmit_reason,
                        created_at=readmit_dt,
                    )
                )
                readmit_count += 1

        # ---------------------------------------------------------------
        # Phase 2: Add transitions for the existing 45 cardiology patients
        # These cover the most recent 0-45 days.
        # ---------------------------------------------------------------

        existing_discharged = (
            Patient.objects.filter(
                hospital=hospital,
                discharge_date__isnull=False,
            )
            .exclude(
                lifecycle_transitions__to_status="discharged",
            )
            .select_related("user")
        )

        existing_count = 0
        for patient in existing_discharged:
            discharge_dt = timezone.make_aware(
                timezone.datetime.combine(patient.discharge_date, timezone.datetime.min.time())
            ) + timedelta(hours=14)

            transitions.append(
                PatientStatusTransition(
                    patient=patient,
                    from_status="post_op",
                    to_status="discharged",
                    triggered_by="clinical_team",
                    reason="Post-operative recovery on track, discharge criteria met",
                    created_at=discharge_dt,
                )
            )
            existing_count += 1

        # Add 1 readmission in the 30-day window (from existing patients)
        # to give a small but non-zero recent rate.
        recent_readmit = (
            Patient.objects.filter(
                hospital=hospital,
                discharge_date__gte=today - timedelta(days=25),
                discharge_date__lte=today - timedelta(days=12),
                lifecycle_status__in=["recovering", "discharged"],
            )
            .exclude(
                lifecycle_transitions__to_status="readmitted",
            )
            .order_by("discharge_date")
            .first()
        )

        if recent_readmit:
            readmit_date = recent_readmit.discharge_date + timedelta(days=5)
            readmit_dt = timezone.make_aware(
                timezone.datetime.combine(readmit_date, timezone.datetime.min.time())
            ) + timedelta(hours=9)

            transitions.append(
                PatientStatusTransition(
                    patient=recent_readmit,
                    from_status="recovering",
                    to_status="readmitted",
                    triggered_by="emergency_department",
                    reason="Post-operative wound dehiscence requiring surgical revision",
                    created_at=readmit_dt,
                )
            )
            readmit_count += 1

        # auto_now_add=True overwrites created_at on save(), so we must:
        # 1. Store desired timestamps before save
        # 2. Save to get the PK
        # 3. Update created_at with the desired timestamp
        desired_timestamps = [(t, t.created_at) for t in transitions]
        for t, desired_ts in desired_timestamps:
            t.save()
            PatientStatusTransition.objects.filter(pk=t.pk).update(created_at=desired_ts)

        self.stdout.write(
            f"  {historical_created} historical patients, "
            f"{existing_count} existing patient transitions, "
            f"{readmit_count} readmissions"
        )

    # -----------------------------------------------------------------------
    # DailyMetrics — 90 days of hand-crafted program data
    # -----------------------------------------------------------------------

    def _create_daily_metrics(self, hospital):
        """Create 90 days of DailyMetrics with a compelling narrative arc.

        The story: a new program ramping up, improving outcomes over time.
        - Early: high readmission rate, few patients, low engagement
        - Mid: growing census, improving engagement, rate dropping
        - Recent: strong engagement, low readmission rate, good check-in compliance
        """
        self.stdout.write("Creating DailyMetrics (90 days)...")

        today = date.today()
        rows = []

        # Hand-crafted data points: (days_ago, metrics_dict)
        # We define key data points and interpolate between them
        for days_ago in range(90, -1, -1):
            d = today - timedelta(days=days_ago)
            is_weekend = d.weekday() >= 5
            phase = self._get_phase(days_ago)

            m = self._metrics_for_day(days_ago, phase, is_weekend)

            # Hospital-specific row
            rows.append(
                DailyMetrics(
                    date=d,
                    hospital=hospital,
                    **m,
                )
            )

            # Aggregate row (hospital=NULL) — same values for single-hospital demo
            rows.append(
                DailyMetrics(
                    date=d,
                    hospital=None,
                    **m,
                )
            )

        DailyMetrics.objects.bulk_create(rows, ignore_conflicts=True)
        self.stdout.write(f"  {len(rows)} DailyMetrics rows created")

    def _get_phase(self, days_ago):
        """Determine narrative phase based on how long ago."""
        if days_ago >= 60:
            return "early"  # Program just started
        elif days_ago >= 30:
            return "growing"  # Building momentum
        else:
            return "mature"  # Running well

    def _metrics_for_day(self, days_ago, phase, is_weekend):  # noqa: C901
        """Hand-craft metrics for a single day based on narrative phase.

        These numbers tell the story of a program that works.
        """
        # --- Patient census ---
        if phase == "early":
            total = 12 + (90 - days_ago) // 3  # 12 → ~22
            active = total - 2
        elif phase == "growing":
            total = 22 + (60 - days_ago) // 2  # 22 → 37
            active = total - 3
        else:
            total = 37 + (30 - days_ago) // 3  # 37 → 47
            active = total - 4

        new = 1 if not is_weekend else 0
        if days_ago % 7 == 0:
            new = 2  # Batch admits on surgery days

        # --- Messages (lower on weekends) ---
        if phase == "early":
            msgs_sent = 8 if not is_weekend else 3
            msgs_recv = 5 if not is_weekend else 2
        elif phase == "growing":
            msgs_sent = 18 if not is_weekend else 8
            msgs_recv = 14 if not is_weekend else 5
        else:
            msgs_sent = 32 if not is_weekend else 14
            msgs_recv = 26 if not is_weekend else 10

        # --- Escalations ---
        if phase == "early":
            escalations = 2 if not is_weekend else 1
            critical = 1 if days_ago % 5 == 0 else 0
        elif phase == "growing":
            escalations = 3 if not is_weekend else 1
            critical = 1 if days_ago % 7 == 0 else 0
        else:
            escalations = 2 if not is_weekend else 1
            critical = 1 if days_ago % 10 == 0 else 0

        # --- Response time (improving over phases) ---
        if phase == "early":
            avg_response = 45.0  # 45 minutes — still figuring out workflow
        elif phase == "growing":
            avg_response = 22.0  # 22 minutes — getting faster
        else:
            avg_response = 12.0  # 12 minutes — dialed in

        # Add some day-to-day variability
        if days_ago % 3 == 0:
            avg_response += 8
        if is_weekend:
            avg_response += 15

        # --- Readmission tracking ---
        if phase == "early":
            discharges = 1 if not is_weekend else 0
            readmissions = 1 if days_ago % 8 == 0 else 0
            rate = 12.5 if discharges > 0 else None
        elif phase == "growing":
            discharges = 2 if not is_weekend else 0
            readmissions = 1 if days_ago % 12 == 0 else 0
            rate = 8.0 if discharges > 0 else None
        else:
            discharges = 2 if not is_weekend else 1
            readmissions = 1 if days_ago % 18 == 0 else 0
            rate = 5.5 if discharges > 0 else None

        # --- Check-in engagement ---
        if phase == "early":
            checkin_sent = 4 if not is_weekend else 2
            checkin_done = 2 if not is_weekend else 1
        elif phase == "growing":
            checkin_sent = 10 if not is_weekend else 4
            checkin_done = 7 if not is_weekend else 3
        else:
            checkin_sent = 18 if not is_weekend else 8
            checkin_done = 15 if not is_weekend else 7

        completion_rate = round(checkin_done / checkin_sent * 100, 1) if checkin_sent else None
        active_with_msgs = (
            int(active * 0.4)
            if phase == "early"
            else (int(active * 0.65) if phase == "growing" else int(active * 0.82))
        )

        # --- Escalation detail ---
        pending = 1 if escalations > 1 else 0
        acknowledged = escalations - pending - (1 if escalations > 2 else 0)
        resolved = escalations - pending - acknowledged
        sla_breaches = 1 if phase == "early" and days_ago % 10 == 0 else 0
        ack_time = avg_response * 0.6

        return {
            "total_patients": total,
            "active_patients": active,
            "new_patients": new,
            "messages_sent": msgs_sent,
            "messages_received": msgs_recv,
            "escalations": escalations,
            "critical_escalations": critical,
            "avg_response_time": round(avg_response, 1),
            "discharges": discharges,
            "readmissions": readmissions,
            "readmission_rate": rate,
            "checkin_sent": checkin_sent,
            "checkin_completions": checkin_done,
            "checkin_completion_rate": completion_rate,
            "active_patients_with_messages": active_with_msgs,
            "pending_escalations": pending,
            "acknowledged_escalations": max(acknowledged, 0),
            "resolved_escalations": max(resolved, 0),
            "sla_breaches": sla_breaches,
            "avg_acknowledgment_time_minutes": round(ack_time, 1),
        }
