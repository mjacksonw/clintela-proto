"""Management command to create a test patient with auth URL."""

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.tokens import short_code_token_generator
from apps.patients.models import Hospital, Patient


class Command(BaseCommand):
    """Create a test patient and print the auth URL."""

    help = "Create a test patient with auth URL for development"

    def handle(self, *args, **options):
        # Create or get hospital
        hospital, created = Hospital.objects.get_or_create(
            code="TEST",
            defaults={
                "name": "Test Hospital",
                "address": "123 Medical Center Dr",
                "phone": "555-0100",
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created hospital: {hospital.name}"))
        else:
            self.stdout.write(f"Hospital already exists: {hospital.name}")

        # Create or get user
        user, created = User.objects.get_or_create(
            username="sarah.chen",
            defaults={
                "first_name": "Sarah",
                "last_name": "Chen",
                "role": "patient",
                "email": "sarah.chen@example.com",
                "phone_number": "555-0101",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created user: {user.get_full_name()}"))
        else:
            self.stdout.write(f"User already exists: {user.get_full_name()}")

        # Create or get patient
        leaflet_code = short_code_token_generator.generate_short_code()
        patient, created = Patient.objects.get_or_create(
            user=user,
            defaults={
                "hospital": hospital,
                "date_of_birth": date(1985, 6, 15),
                "leaflet_code": leaflet_code,
                "surgery_type": "Knee Replacement",
                "surgery_date": date.today() - timedelta(days=14),
                "discharge_date": date.today() - timedelta(days=12),
                "status": "green",
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created patient: {patient}"))
        else:
            self.stdout.write(f"Patient already exists: {patient}")

        # Generate auth URL
        token = short_code_token_generator.make_token(patient)
        code = short_code_token_generator.get_short_code(token)
        auth_url = f"/accounts/start/?code={code}&token={token}&patient_id={patient.pk}"

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Test Patient Auth URL:"))
        self.stdout.write(self.style.SUCCESS(f"  http://localhost:8000{auth_url}"))
        self.stdout.write(self.style.SUCCESS("  DOB: 06/15/1985"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
