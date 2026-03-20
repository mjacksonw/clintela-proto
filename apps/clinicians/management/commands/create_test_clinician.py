"""Management command to create test clinician with sample data."""

import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.agents.models import AgentConversation, AgentMessage, Escalation
from apps.clinicians.models import Clinician, ClinicianAvailability
from apps.patients.models import Hospital, Patient


class Command(BaseCommand):
    help = "Create a test clinician with hospital, patients, escalations, and conversations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="dr_smith",
            help="Username for the clinician (default: dr_smith)",
        )
        parser.add_argument(
            "--password",
            default="testpass123",
            help="Password for the clinician (default: testpass123)",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]

        # Create hospital
        hospital, _ = Hospital.objects.get_or_create(
            code="MGH",
            defaults={
                "name": "Metro General Hospital",
                "address": "123 Medical Center Dr",
            },
        )
        self.stdout.write(f"Hospital: {hospital.name}")

        # Create clinician user
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": "Sarah",
                "last_name": "Smith",
                "email": f"{username}@clintela.test",
                "role": "clinician",
            },
        )
        if created:
            user.set_password(password)
            user.save()

        # Create clinician profile
        clinician, _ = Clinician.objects.get_or_create(
            user=user,
            defaults={
                "role": "physician",
                "specialty": "Orthopedic Surgery",
                "is_active": True,
            },
        )
        clinician.hospitals.add(hospital)
        self.stdout.write(f"Clinician: {user.get_full_name()} ({username})")

        # Set availability (Mon-Fri 7am-7pm)
        for day in range(5):
            ClinicianAvailability.objects.get_or_create(
                clinician=clinician,
                day_of_week=day,
                start_time="07:00",
                is_recurring=True,
                defaults={"end_time": "19:00"},
            )

        # Create 5 test patients at varying triage levels
        statuses = ["red", "orange", "yellow", "green", "green"]
        lifecycles = ["post_op", "recovering", "post_op", "discharged", "recovering"]
        surgery_types = [
            "Total Knee Replacement",
            "Hip Replacement",
            "ACL Reconstruction",
            "Rotator Cuff Repair",
            "Spinal Fusion",
        ]
        patient_names = [
            ("Alice", "Johnson"),
            ("Bob", "Williams"),
            ("Carol", "Davis"),
            ("David", "Martinez"),
            ("Emma", "Thompson"),
        ]

        patients = []
        for i, (first, last) in enumerate(patient_names):
            p_user, p_created = User.objects.get_or_create(
                username=f"patient_{first.lower()}",
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{first.lower()}@patient.test",
                    "role": "patient",
                    "phone_number": f"+1555010{i:04d}",
                },
            )
            if p_created:
                p_user.set_password("testpass123")
                p_user.save()

            patient, _ = Patient.objects.get_or_create(
                user=p_user,
                defaults={
                    "hospital": hospital,
                    "status": statuses[i],
                    "lifecycle_status": lifecycles[i],
                    "surgery_type": surgery_types[i],
                    "surgery_date": timezone.now() - timedelta(days=random.randint(3, 21)),  # noqa: S311
                    "date_of_birth": date(1950 + i * 5, 3, 15),
                    "mrn": f"MRN-{1000 + i}",
                    "leaflet_code": f"LC-{first.upper()}-{1000 + i}",
                    "is_active": True,
                },
            )
            patients.append(patient)
            self.stdout.write(f"  Patient: {p_user.get_full_name()} ({statuses[i]})")

        # Create conversations with messages for each patient
        for patient in patients:
            conv, _ = AgentConversation.objects.get_or_create(
                patient=patient,
                agent_type="supervisor",
                clinician=None,
                defaults={"status": "active"},
            )

            # Add a few messages
            if not conv.messages.exists():
                AgentMessage.objects.create(
                    conversation=conv,
                    role="user",
                    content=f"Hi, I'm {patient.user.first_name}. I had {patient.surgery_type} recently.",
                )
                AgentMessage.objects.create(
                    conversation=conv,
                    role="assistant",
                    agent_type="care_coordinator",
                    content=(
                        f"Hello {patient.user.first_name}! I'm here to help "
                        f"with your recovery. How are you feeling today?"
                    ),
                )

        # Create escalations for critical/urgent patients
        for patient in patients[:2]:
            severity = "critical" if patient.status == "red" else "urgent"
            Escalation.objects.get_or_create(
                patient=patient,
                status="pending",
                defaults={
                    "reason": (
                        f"Patient reporting "
                        f"{'severe pain and swelling' if severity == 'critical' else 'increased discomfort'} "
                        f"post-{patient.surgery_type}."
                    ),
                    "severity": severity,
                    "escalation_type": "clinical",
                    "conversation_summary": (
                        f"AI conversation with {patient.user.get_full_name()} flagged for clinician review."
                    ),
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTest clinician created successfully!\n"
                f"  Login: {username} / {password}\n"
                f"  URL: /clinician/login/\n"
                f"  {len(patients)} patients, 2 escalations"
            )
        )
