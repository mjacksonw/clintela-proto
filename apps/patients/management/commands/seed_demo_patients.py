"""Management command to create demo patients with rich preference profiles."""

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.tokens import short_code_token_generator
from apps.patients.models import Hospital, Patient, PatientPreferences

# Rich patient profiles for demos — each tells a story
DEMO_PATIENTS = [
    {
        "username": "maria.chen",
        "first_name": "Maria",
        "last_name": "Chen",
        "dob": date(1954, 3, 12),
        "surgery_type": "CABG (Coronary Artery Bypass)",
        "days_post_op": 8,
        "status": "yellow",
        "lifecycle_status": "recovering",
        "preferences": {
            "preferred_name": "Maria",
            "about_me": (
                "Retired high school English teacher — 35 years in the classroom. "
                "I like to understand the 'why' behind things. I live alone in a "
                "second-floor walk-up in Queens. My daughter Emily visits on weekends, "
                "and my neighbor Mrs. Kowalski checks in every morning."
            ),
            "living_situation": "Lives alone, second-floor apartment, no elevator",
            "daily_routines": "Morning person — up by 6:30. Tea and crossword before anything else.",
            "recovery_goals": (
                "Back to my book club by April, weekly walks in Flushing Meadows Park, "
                "cooking dinner for Emily and the grandkids"
            ),
            "values": "Independence, lifelong learning, family dinners on Sundays",
            "concerns": (
                "Managing the stairs — I worry about slipping. Being alone at night. "
                "Keeping track of all these medications."
            ),
            "communication_style": "detailed",
            "preferred_contact_time": "Mornings, before 10am",
            "support_network": (
                "Daughter Emily (visits weekends), neighbor Mrs. Kowalski (daily check-in), book club friends who call"
            ),
        },
    },
    {
        "username": "jimmy.okafor",
        "first_name": "James",
        "last_name": "Okafor",
        "dob": date(1968, 9, 28),
        "surgery_type": "Total Hip Replacement",
        "days_post_op": 5,
        "status": "green",
        "lifecycle_status": "recovering",
        "preferences": {
            "preferred_name": "Jimmy",
            "about_me": (
                "Construction foreman — been building things my whole life. "
                "Just need to get back on my feet and back to work. "
                "My wife Adunni handles the morning routine with our son Kelechi."
            ),
            "living_situation": "Lives with wife Adunni and teenage son Kelechi (16)",
            "daily_routines": "Usually up at 5am for work. Evenings are family time.",
            "recovery_goals": ("Back on job sites by summer, coaching Kelechi's basketball team in the fall"),
            "values": "Providing for my family, hard work, being a good role model for my son",
            "concerns": (
                "How long until I can work again — we need my income. "
                "Will I be able to do the physical parts of my job?"
            ),
            "communication_style": "direct",
            "preferred_contact_time": "Evenings after 6pm — wife handles mornings",
            "support_network": "Wife Adunni (full-time support), son Kelechi helps around the house",
        },
    },
    {
        "username": "priya.sharma",
        "first_name": "Priya",
        "last_name": "Sharma",
        "dob": date(1981, 1, 5),
        "surgery_type": "Knee Arthroscopy",
        "days_post_op": 3,
        "status": "green",
        "lifecycle_status": "recovering",
        "preferences": {
            "preferred_name": "Priya",
            "about_me": (
                "Software engineer, work from home. Two kids — Ananya (11) and Dev (8). "
                "I'm the one who does school drop-offs and weekend soccer. "
                "Feeling guilty about my husband picking up all the slack."
            ),
            "living_situation": "Lives with husband Rajan and two children in a single-story home",
            "daily_routines": "Work 9-5 from home office. Kids' activities dominate evenings and weekends.",
            "recovery_goals": (
                "Running 5Ks again, taking the kids to Saturday soccer, walking the dog without limping"
            ),
            "values": "Being present for my kids, staying active, not being a burden on anyone",
            "concerns": (
                "Being a burden on Rajan — he's already stretched thin. "
                "When can I drive the kids to school again? Will my knee ever feel normal?"
            ),
            "communication_style": "direct",
            "preferred_contact_time": "Flexible — anytime during work hours is fine",
            "support_network": ("Husband Rajan (taking time off work), mother-in-law helps with kids on Tuesdays"),
        },
    },
    {
        "username": "bobby.tran",
        "first_name": "Robert",
        "last_name": "Tran",
        "dob": date(1945, 7, 4),
        "surgery_type": "Pacemaker Implantation",
        "days_post_op": 12,
        "status": "green",
        "lifecycle_status": "recovering",
        "preferences": {
            "preferred_name": "Bobby",
            "about_me": (
                "Retired postal worker, Vietnam veteran. Married 55 years to my wife Linh. "
                "My wife worries enough for both of us — I just want to know what's normal. "
                "Hard of hearing, so I prefer text over phone calls."
            ),
            "living_situation": "Lives with wife Linh, adult children visit weekly",
            "daily_routines": (
                "Slow mornings with Linh. Afternoon in the garden if weather allows. "
                "VA appointment every other Thursday."
            ),
            "recovery_goals": (
                "Tend my vegetable garden this spring, "
                "drive myself to VA appointments again, "
                "walk to the corner store without getting winded"
            ),
            "values": "Self-reliance, growing things, routine, not worrying Linh",
            "concerns": (
                "Gardening restrictions — how soon can I dig and lift? "
                "Driving to VA — need to be cleared. "
                "The pacemaker — will I set off metal detectors?"
            ),
            "communication_style": "conversational",
            "preferred_contact_time": "Afternoons — mornings are slow",
            "language_preferences": "English is fine, but simple words — hearing aid doesn't catch everything",
            "support_network": (
                "Wife Linh (always there), son Michael (Sundays), daughter Kim (calls twice a week), VA buddy group"
            ),
        },
    },
]


class Command(BaseCommand):
    """Create demo patients with rich preference profiles for demonstrations."""

    help = "Create 4 demo patients with rich backstories and preferences"

    def handle(self, *args, **options):
        # Use the same hospital as the main demo fixtures (clinicians, patient list) — code SJMC.
        # A separate DEMO hospital left demo patients invisible to dr_smith and broke deep links.
        hospital = Hospital.objects.filter(code="SJMC").first()
        if not hospital:
            hospital, _ = Hospital.objects.get_or_create(
                code="DEMO",
                defaults={
                    "name": "Metro General Hospital",
                    "address": "500 First Avenue, New York, NY 10016",
                    "phone": "212-555-0100",
                    "is_active": True,
                },
            )
        self.stdout.write(f"Hospital: {hospital.name}")

        for profile in DEMO_PATIENTS:
            user, created = User.objects.get_or_create(
                username=profile["username"],
                defaults={
                    "first_name": profile["first_name"],
                    "last_name": profile["last_name"],
                    "role": "patient",
                    "email": f"{profile['username']}@example.com",
                },
            )

            leaflet_code = short_code_token_generator.generate_short_code()
            patient, p_created = Patient.objects.get_or_create(
                user=user,
                defaults={
                    "hospital": hospital,
                    "date_of_birth": profile["dob"],
                    "leaflet_code": leaflet_code,
                    "surgery_type": profile["surgery_type"],
                    "surgery_date": date.today() - timedelta(days=profile["days_post_op"]),
                    "discharge_date": date.today() - timedelta(days=max(profile["days_post_op"] - 2, 0)),
                    "status": profile["status"],
                    "lifecycle_status": profile["lifecycle_status"],
                    "is_active": True,
                },
            )

            # Create or update preferences
            prefs_data = profile["preferences"]
            prefs, _ = PatientPreferences.objects.update_or_create(
                patient=patient,
                defaults=prefs_data,
            )

            # Generate auth URL
            token = short_code_token_generator.make_token(patient)
            code = short_code_token_generator.get_short_code(token)
            auth_url = f"/accounts/start/?code={code}&token={token}&patient_id={patient.pk}"

            status = "Created" if p_created else "Updated"
            name = prefs_data.get("preferred_name", profile["first_name"])
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {status}: {name} ({profile['first_name']} {profile['last_name']}) "
                    f"— {profile['surgery_type']}, Day {profile['days_post_op']}"
                )
            )
            self.stdout.write(f"    About: {prefs_data['about_me'][:80]}...")
            self.stdout.write(f"    Goals: {prefs_data['recovery_goals'][:80]}...")
            self.stdout.write(f"    Auth:  http://localhost:8000{auth_url}")
            self.stdout.write(f"    DOB:   {profile['dob'].strftime('%m/%d/%Y')}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS(f"  {len(DEMO_PATIENTS)} demo patients ready"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
