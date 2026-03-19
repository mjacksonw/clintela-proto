"""Management command to seed test pathways."""

from django.core.management.base import BaseCommand

from apps.pathways.models import ClinicalPathway, PathwayMilestone


class Command(BaseCommand):
    """Seed database with test clinical pathways."""

    help = "Create test clinical pathways for development"

    def handle(self, *args, **options):
        """Create test pathways."""
        self.stdout.write("Creating test pathways...")

        # General Surgery Pathway (30 days)
        general_surgery, _ = ClinicalPathway.objects.get_or_create(
            name="General Surgery Recovery",
            surgery_type="General Surgery",
            defaults={
                "description": "Standard recovery pathway for general surgery patients",
                "duration_days": 30,
                "is_active": True,
            },
        )

        # Create milestones for General Surgery
        milestones = [
            {
                "day": 1,
                "phase": "early",
                "title": "Immediate Post-Op",
                "description": "First 24 hours after surgery",
                "expected_symptoms": ["pain 3-6/10", "fatigue", "nausea", "drowsiness"],
                "activities": ["rest", "hydration", "short walks to bathroom"],
                "red_flags": ["fever >101°F", "severe bleeding", "chest pain", "difficulty breathing"],
                "check_in_questions": [
                    "How is your pain on a scale of 1-10?",
                    "Are you able to keep down fluids?",
                    "Are you able to walk to the bathroom?",
                ],
            },
            {
                "day": 3,
                "phase": "early",
                "title": "Early Recovery",
                "description": "Days 2-3: Managing initial recovery",
                "expected_symptoms": ["pain 2-4/10", "fatigue", "incision soreness"],
                "activities": ["short walks", "light meals", "hydration"],
                "red_flags": ["fever >101°F", "increasing pain", "redness at incision", "pus/discharge"],
                "check_in_questions": [
                    "How is your pain today?",
                    "Is your incision healing well?",
                    "Are you eating and drinking normally?",
                ],
            },
            {
                "day": 7,
                "phase": "middle",
                "title": "First Week Milestone",
                "description": "One week post-surgery check-in",
                "expected_symptoms": ["pain 1-3/10", "some fatigue", "itching at incision"],
                "activities": ["light activity", "short walks", "normal diet"],
                "red_flags": ["fever", "increasing pain", "signs of infection"],
                "check_in_questions": [
                    "How is your energy level?",
                    "Are you able to do light activities?",
                    "Any concerns about your incision?",
                ],
            },
            {
                "day": 14,
                "phase": "middle",
                "title": "Two Week Check-In",
                "description": "Two weeks post-surgery progress",
                "expected_symptoms": ["minimal pain", "normal energy", "healing incision"],
                "activities": ["moderate activity", "regular walks", "light household tasks"],
                "red_flags": ["new pain", "swelling", "redness", "fever"],
                "check_in_questions": [
                    "How is your overall recovery going?",
                    "Are you back to normal activities?",
                    "Any new symptoms or concerns?",
                ],
            },
            {
                "day": 30,
                "phase": "late",
                "title": "Recovery Complete",
                "description": "Final recovery milestone",
                "expected_symptoms": ["no pain", "normal energy", "fully healed incision"],
                "activities": ["normal activities", "regular exercise"],
                "red_flags": ["any new severe symptoms"],
                "check_in_questions": [
                    "How do you feel overall?",
                    "Are you back to your normal routine?",
                    "Any lingering concerns?",
                ],
            },
        ]

        for m in milestones:
            PathwayMilestone.objects.get_or_create(
                pathway=general_surgery,
                day=m["day"],
                defaults={
                    "phase": m["phase"],
                    "title": m["title"],
                    "description": m["description"],
                    "expected_symptoms": m["expected_symptoms"],
                    "activities": m["activities"],
                    "red_flags": m["red_flags"],
                    "check_in_questions": m["check_in_questions"],
                },
            )

        self.stdout.write(self.style.SUCCESS(f"Created General Surgery pathway with {len(milestones)} milestones"))

        # Cardiac Surgery Pathway (60 days)
        cardiac_surgery, _ = ClinicalPathway.objects.get_or_create(
            name="Cardiac Surgery Recovery",
            surgery_type="Cardiac Surgery",
            defaults={
                "description": "Recovery pathway for cardiac surgery patients",
                "duration_days": 60,
                "is_active": True,
            },
        )

        # Create milestones for Cardiac Surgery
        cardiac_milestones = [
            {
                "day": 1,
                "phase": "early",
                "title": "Immediate Post-Op",
                "description": "First 24 hours after cardiac surgery",
                "expected_symptoms": ["chest discomfort", "fatigue", "sore throat", "nausea"],
                "activities": ["ICU monitoring", "rest", "breathing exercises"],
                "red_flags": ["chest pain", "irregular heartbeat", "difficulty breathing", "fever >101°F"],
                "check_in_questions": [
                    "How is your chest discomfort?",
                    "Are you doing your breathing exercises?",
                    "Any concerns about your heart rhythm?",
                ],
            },
            {
                "day": 7,
                "phase": "early",
                "title": "First Week",
                "description": "First week of cardiac recovery",
                "expected_symptoms": ["chest soreness", "fatigue", "appetite changes"],
                "activities": ["short walks", "breathing exercises", "rest"],
                "red_flags": ["chest pain", "palpitations", "dizziness", "swelling"],
                "check_in_questions": [
                    "How is your energy level?",
                    "Are you able to walk short distances?",
                    "Any chest discomfort or palpitations?",
                ],
            },
            {
                "day": 14,
                "phase": "middle",
                "title": "Two Week Check-In",
                "description": "Two weeks post-cardiac surgery",
                "expected_symptoms": ["decreasing chest discomfort", "improving energy"],
                "activities": ["daily walks", "light activities", "cardiac rehab prep"],
                "red_flags": ["chest pain", "shortness of breath", "leg swelling", "dizziness"],
                "check_in_questions": [
                    "How is your recovery progressing?",
                    "Are you walking daily?",
                    "Any new symptoms?",
                ],
            },
            {
                "day": 30,
                "phase": "middle",
                "title": "One Month Milestone",
                "description": "One month post-cardiac surgery",
                "expected_symptoms": ["minimal chest discomfort", "good energy"],
                "activities": ["cardiac rehab", "moderate activity", "driving (if cleared)"],
                "red_flags": ["chest pain", "irregular heartbeat", "excessive fatigue"],
                "check_in_questions": [
                    "How is cardiac rehab going?",
                    "Are you following your activity restrictions?",
                    "Any concerns about returning to activities?",
                ],
            },
            {
                "day": 60,
                "phase": "late",
                "title": "Recovery Complete",
                "description": "Two months post-cardiac surgery",
                "expected_symptoms": ["no chest discomfort", "normal energy"],
                "activities": ["normal activities", "continued cardiac rehab", "regular exercise"],
                "red_flags": ["any cardiac symptoms"],
                "check_in_questions": [
                    "How do you feel overall?",
                    "Are you back to your normal routine?",
                    "Any concerns about your heart?",
                ],
            },
        ]

        for m in cardiac_milestones:
            PathwayMilestone.objects.get_or_create(
                pathway=cardiac_surgery,
                day=m["day"],
                defaults={
                    "phase": m["phase"],
                    "title": m["title"],
                    "description": m["description"],
                    "expected_symptoms": m["expected_symptoms"],
                    "activities": m["activities"],
                    "red_flags": m["red_flags"],
                    "check_in_questions": m["check_in_questions"],
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created Cardiac Surgery pathway with {len(cardiac_milestones)} milestones"
            )
        )

        self.stdout.write(self.style.SUCCESS("\nTest pathways created successfully!"))
