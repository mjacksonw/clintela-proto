"""Management command to create a bustling cardiology service with realistic demo data."""

import random  # nosec: B311 - Used for demo data generation only
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.agents.models import AgentConversation, AgentMessage, Escalation
from apps.caregivers.models import Caregiver, CaregiverInvitation, CaregiverRelationship
from apps.clinicians.models import Appointment, Clinician, ClinicianNote
from apps.pathways.models import ClinicalPathway, PatientMilestoneCheckin, PatientPathway
from apps.patients.models import ConsentRecord, Hospital, Patient


class Command(BaseCommand):
    help = "Create a bustling cardiology service with 45 patients, rich conversations, and realistic activity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-existing",
            action="store_true",
            help="Keep existing patient data (default: deletes patients, keeps clinicians)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Creating Cardiology Service demo data...")
        self.stdout.write("")

        if not options["keep_existing"]:
            self._clear_existing_patient_data()

        # Create or get St. Jude Medical Center
        hospital = self._create_hospital()
        self.stdout.write(f"Hospital: {hospital.name}")

        # Get existing clinicians
        clinicians = self._get_clinicians()
        if not clinicians:
            self.stdout.write(self.style.ERROR("No clinicians found. Run create_test_clinician first."))
            return

        self.stdout.write(f"Clinicians: {len(clinicians)}")
        for c in clinicians:
            self.stdout.write(f"  - {c.user.get_full_name()} ({c.specialty})")

        # Create patients
        patients = self._create_patients(hospital, clinicians)
        self.stdout.write(f"\nCreated {len(patients)} patients")

        # Create pathways and milestones
        self._create_patient_pathways(patients)

        # Create conversations with realistic content
        self._create_conversations(patients)

        # Create escalations
        self._create_escalations(patients, clinicians)

        # Create appointments
        self._create_appointments(patients, clinicians)

        # Create caregivers
        self._create_caregivers(patients)

        # Create clinician notes
        self._create_clinician_notes(patients, clinicians)

        # Create consent records
        self._create_consent_records(patients)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Cardiology Service created successfully!\n"
                f"  - {len(patients)} cardiac surgery patients\n"
                f"  - Multiple surgery types (CABG, Valve, PCI, etc.)\n"
                f"  - Virtual visits at days 3, 10, 21\n"
                f"  - Rich conversation history\n"
                f"  - Active escalations and appointments"
            )
        )

    def _clear_existing_patient_data(self):
        """Clear existing patient data while preserving clinicians."""
        self.stdout.write("Clearing existing patient data...")

        # Delete patient-related data (preserves clinicians, hospitals)
        PatientMilestoneCheckin.objects.all().delete()
        PatientPathway.objects.all().delete()
        CaregiverRelationship.objects.all().delete()
        CaregiverInvitation.objects.all().delete()
        Caregiver.objects.all().delete()
        ConsentRecord.objects.all().delete()
        Appointment.objects.all().delete()
        ClinicianNote.objects.all().delete()
        Escalation.objects.all().delete()
        AgentMessage.objects.all().delete()
        AgentConversation.objects.all().delete()

        # Delete patients and their users
        patients = Patient.objects.all()
        patient_user_ids = list(patients.values_list("user_id", flat=True))
        patients.delete()
        User.objects.filter(id__in=patient_user_ids).delete()

        self.stdout.write("  Existing patient data cleared.")

    def _create_hospital(self) -> Hospital:
        """Create St. Jude Medical Center."""
        hospital, _ = Hospital.objects.get_or_create(
            code="SJMC",
            defaults={
                "name": "St. Jude Medical Center",
                "address": "1500 Heart Care Way, Cardiac City, CC 90210",
                "phone": "+1 (555) HEART-1",
            },
        )
        return hospital

    def _get_clinicians(self) -> list[Clinician]:
        """Get existing clinicians or return empty if none."""
        clinicians = list(Clinician.objects.filter(is_active=True))
        return clinicians

    def _create_patients(self, hospital: Hospital, clinicians: list[Clinician]) -> list[Patient]:
        """Create 45 cardiac surgery patients with varied profiles."""
        self.stdout.write("\nCreating patients...")

        # Patient definitions with realistic profiles
        patient_definitions = [
            # CABG patients (16) - most common
            # Critical/Orange
            {
                "name": ("Robert", "Chen"),
                "age": 67,
                "surgery": "CABG",
                "days_ago": 2,
                "status": "red",
                "lifecycle": "post_op",
            },
            {
                "name": ("Patricia", "Williams"),
                "age": 71,
                "surgery": "CABG",
                "days_ago": 5,
                "status": "orange",
                "lifecycle": "post_op",
            },
            {
                "name": ("James", "Morrison"),
                "age": 58,
                "surgery": "CABG",
                "days_ago": 3,
                "status": "red",
                "lifecycle": "post_op",
            },
            # Yellow
            {
                "name": ("Linda", "Rodriguez"),
                "age": 64,
                "surgery": "CABG",
                "days_ago": 8,
                "status": "yellow",
                "lifecycle": "discharged",
            },
            {
                "name": ("Michael", "Thompson"),
                "age": 69,
                "surgery": "CABG",
                "days_ago": 12,
                "status": "yellow",
                "lifecycle": "recovering",
            },
            {
                "name": ("Susan", "Davis"),
                "age": 62,
                "surgery": "CABG",
                "days_ago": 15,
                "status": "yellow",
                "lifecycle": "recovering",
            },
            {
                "name": ("William", "Anderson"),
                "age": 74,
                "surgery": "CABG",
                "days_ago": 6,
                "status": "yellow",
                "lifecycle": "post_op",
            },
            {
                "name": ("Elizabeth", "Taylor"),
                "age": 66,
                "surgery": "CABG",
                "days_ago": 18,
                "status": "yellow",
                "lifecycle": "recovering",
            },
            # Green
            {
                "name": ("Joseph", "Wilson"),
                "age": 59,
                "surgery": "CABG",
                "days_ago": 25,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Margaret", "Garcia"),
                "age": 68,
                "surgery": "CABG",
                "days_ago": 32,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Thomas", "Martinez"),
                "age": 61,
                "surgery": "CABG",
                "days_ago": 40,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Dorothy", "Robinson"),
                "age": 72,
                "surgery": "CABG",
                "days_ago": 28,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Charles", "Clark"),
                "age": 56,
                "surgery": "CABG",
                "days_ago": 45,
                "status": "green",
                "lifecycle": "recovered",
            },
            {
                "name": ("Barbara", "Hernandez"),
                "age": 65,
                "surgery": "CABG",
                "days_ago": 38,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Daniel", "Lopez"),
                "age": 63,
                "surgery": "CABG",
                "days_ago": 22,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Nancy", "Gonzalez"),
                "age": 70,
                "surgery": "CABG",
                "days_ago": 50,
                "status": "green",
                "lifecycle": "recovered",
            },
            # Aortic Valve Replacement (10)
            # Critical/Orange
            {
                "name": ("David", "Lee"),
                "age": 76,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 4,
                "status": "orange",
                "lifecycle": "post_op",
            },
            {
                "name": ("Jennifer", "White"),
                "age": 72,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 7,
                "status": "orange",
                "lifecycle": "discharged",
            },
            # Yellow
            {
                "name": ("Richard", "Hall"),
                "age": 68,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 14,
                "status": "yellow",
                "lifecycle": "recovering",
            },
            {
                "name": ("Maria", "Young"),
                "age": 74,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 10,
                "status": "yellow",
                "lifecycle": "discharged",
            },
            {
                "name": ("Christopher", "King"),
                "age": 69,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 21,
                "status": "yellow",
                "lifecycle": "recovering",
            },
            # Green
            {
                "name": ("Lisa", "Wright"),
                "age": 65,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 35,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Matthew", "Scott"),
                "age": 71,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 42,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Karen", "Green"),
                "age": 67,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 55,
                "status": "green",
                "lifecycle": "recovered",
            },
            {
                "name": ("Anthony", "Baker"),
                "age": 73,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 30,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Betty", "Adams"),
                "age": 78,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 62,
                "status": "green",
                "lifecycle": "recovered",
            },
            # Mitral Valve Repair/Replacement (8)
            # Orange
            {
                "name": ("Mark", "Nelson"),
                "age": 61,
                "surgery": "Mitral Valve Repair",
                "days_ago": 9,
                "status": "orange",
                "lifecycle": "discharged",
            },
            # Yellow
            {
                "name": ("Sandra", "Carter"),
                "age": 66,
                "surgery": "Mitral Valve Replacement",
                "days_ago": 16,
                "status": "yellow",
                "lifecycle": "recovering",
            },
            {
                "name": ("Paul", "Mitchell"),
                "age": 59,
                "surgery": "Mitral Valve Repair",
                "days_ago": 20,
                "status": "yellow",
                "lifecycle": "recovering",
            },
            {
                "name": ("Ashley", "Perez"),
                "age": 63,
                "surgery": "Mitral Valve Replacement",
                "days_ago": 13,
                "status": "yellow",
                "lifecycle": "discharged",
            },
            # Green
            {
                "name": ("Steven", "Roberts"),
                "age": 57,
                "surgery": "Mitral Valve Repair",
                "days_ago": 33,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Kimberly", "Turner"),
                "age": 64,
                "surgery": "Mitral Valve Replacement",
                "days_ago": 48,
                "status": "green",
                "lifecycle": "recovered",
            },
            {
                "name": ("Andrew", "Phillips"),
                "age": 60,
                "surgery": "Mitral Valve Repair",
                "days_ago": 27,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Donna", "Campbell"),
                "age": 68,
                "surgery": "Mitral Valve Replacement",
                "days_ago": 41,
                "status": "green",
                "lifecycle": "recovering",
            },
            # PCI/Stent (6) - shorter recovery
            # Yellow
            {
                "name": ("Jason", "Parker"),
                "age": 54,
                "surgery": "PCI with Stent",
                "days_ago": 5,
                "status": "yellow",
                "lifecycle": "discharged",
            },
            {
                "name": ("Michelle", "Evans"),
                "age": 58,
                "surgery": "PCI with Stent",
                "days_ago": 11,
                "status": "yellow",
                "lifecycle": "recovering",
            },
            # Green
            {
                "name": ("Ryan", "Edwards"),
                "age": 52,
                "surgery": "PCI with Stent",
                "days_ago": 18,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Stephanie", "Collins"),
                "age": 56,
                "surgery": "PCI with Stent",
                "days_ago": 24,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Jacob", "Stewart"),
                "age": 50,
                "surgery": "PCI with Stent",
                "days_ago": 28,
                "status": "green",
                "lifecycle": "recovered",
            },
            {
                "name": ("Rebecca", "Sanchez"),
                "age": 55,
                "surgery": "PCI with Stent",
                "days_ago": 15,
                "status": "green",
                "lifecycle": "recovering",
            },
            # Pacemaker/ICD (3)
            {
                "name": ("Gary", "Morris"),
                "age": 73,
                "surgery": "Pacemaker/ICD",
                "days_ago": 6,
                "status": "green",
                "lifecycle": "discharged",
            },
            {
                "name": ("Cynthia", "Rogers"),
                "age": 69,
                "surgery": "Pacemaker/ICD",
                "days_ago": 12,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Kenneth", "Reed"),
                "age": 75,
                "surgery": "Pacemaker/ICD",
                "days_ago": 3,
                "status": "yellow",
                "lifecycle": "post_op",
            },
            # Maze Procedure (2)
            {
                "name": ("Emily", "Cook"),
                "age": 62,
                "surgery": "Maze Procedure",
                "days_ago": 19,
                "status": "green",
                "lifecycle": "recovering",
            },
            {
                "name": ("Brian", "Morgan"),
                "age": 59,
                "surgery": "Maze Procedure",
                "days_ago": 35,
                "status": "green",
                "lifecycle": "recovering",
            },
        ]

        # Pre-surgery patients (3)
        pre_surgery = [
            {
                "name": ("Carol", "Bell"),
                "age": 68,
                "surgery": "CABG",
                "days_ago": 0,
                "status": "green",
                "lifecycle": "pre_surgery",
            },
            {
                "name": ("Frank", "Murphy"),
                "age": 71,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 0,
                "status": "green",
                "lifecycle": "pre_surgery",
            },
            {
                "name": ("Helen", "Rivera"),
                "age": 64,
                "surgery": "Mitral Valve Repair",
                "days_ago": 0,
                "status": "green",
                "lifecycle": "pre_surgery",
            },
        ]

        # Currently admitted/in-surgery (2)
        admitted = [
            {
                "name": ("Arthur", "Cooper"),
                "age": 66,
                "surgery": "CABG",
                "days_ago": 0,
                "status": "yellow",
                "lifecycle": "admitted",
            },
            {
                "name": ("Joyce", "Ward"),
                "age": 74,
                "surgery": "Aortic Valve Replacement",
                "days_ago": 0,
                "status": "green",
                "lifecycle": "in_surgery",
            },
        ]

        # Readmitted patients (2)
        readmitted = [
            {
                "name": ("Ralph", "Torres"),
                "age": 63,
                "surgery": "CABG",
                "days_ago": 1,
                "status": "orange",
                "lifecycle": "admitted",
            },
            {
                "name": ("Anna", "Peterson"),
                "age": 67,
                "surgery": "Mitral Valve Replacement",
                "days_ago": 2,
                "status": "red",
                "lifecycle": "admitted",
            },
        ]

        all_patients = patient_definitions + pre_surgery + admitted + readmitted
        created_patients = []

        for i, p_def in enumerate(all_patients):
            first_name, last_name = p_def["name"]
            age = p_def["age"]
            surgery_type = p_def["surgery"]
            days_ago = p_def["days_ago"]
            status = p_def["status"]
            lifecycle = p_def["lifecycle"]

            # Calculate dates
            dob = date.today().replace(year=date.today().year - age)
            if lifecycle in ["pre_surgery", "admitted", "in_surgery"]:
                surgery_date = None
                discharge_date = None
            else:
                surgery_date = date.today() - timedelta(days=days_ago)
                discharge_date = surgery_date + timedelta(days=2) if days_ago > 2 else None

            # Create user
            username = f"cardiac_{first_name.lower()}_{last_name.lower()}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": f"{username}@patient.test",
                    "role": "patient",
                    "phone_number": f"+1555200{i:04d}",
                },
            )
            if created:
                user.set_password("testpass123")
                user.save()

            # Create patient
            patient, _ = Patient.objects.get_or_create(
                user=user,
                defaults={
                    "hospital": hospital,
                    "date_of_birth": dob,
                    "mrn": f"SJ-2026-{4000 + i:04d}",
                    "leaflet_code": f"SJ-{first_name.upper()[:3]}{last_name.upper()[:3]}-{1000 + i}",
                    "surgery_type": surgery_type,
                    "surgery_date": surgery_date,
                    "discharge_date": discharge_date,
                    "status": status,
                    "lifecycle_status": lifecycle,
                    "is_active": True,
                },
            )

            # Assign to a clinician (distribute evenly)
            clinician = clinicians[i % len(clinicians)]
            if hospital not in clinician.hospitals.all():
                clinician.hospitals.add(hospital)

            created_patients.append(patient)
            self.stdout.write(f"  {first_name} {last_name} - {surgery_type} ({status})")

        return created_patients

    def _create_patient_pathways(self, patients: list[Patient]):
        """Create pathway assignments and milestone check-ins."""
        self.stdout.write("\nCreating pathways and milestone check-ins...")

        for patient in patients:
            if not patient.surgery_type:
                continue

            # Get appropriate pathway
            pathway = ClinicalPathway.objects.filter(surgery_type=patient.surgery_type, is_active=True).first()

            if not pathway:
                continue

            # Create patient pathway
            patient_pathway, _ = PatientPathway.objects.get_or_create(
                patient=patient,
                pathway=pathway,
                defaults={
                    "status": "active",
                    "started_at": patient.surgery_date or timezone.now(),
                },
            )

            # Create milestone check-ins
            if patient.surgery_date:
                days_post_op = (date.today() - patient.surgery_date).days

                for milestone in pathway.milestones.all():
                    # Determine status based on timing
                    if milestone.day <= days_post_op:
                        # Milestone day has passed
                        if milestone.day <= days_post_op - 3:
                            # Completed if it's been 3+ days
                            checkin_status = {
                                "completed": True,
                                "completed_at": patient.surgery_date + timedelta(days=milestone.day),
                            }
                        else:
                            # Recently passed, might be pending
                            checkin_status = {
                                "completed": random.choice([True, False]),  # nosec: B311
                                "completed_at": patient.surgery_date + timedelta(days=milestone.day)  # nosec: B311
                                if random.choice([True, False])  # nosec: B311
                                else None,
                            }
                    else:
                        # Future milestone
                        checkin_status = {"completed": False, "completed_at": None}

                    PatientMilestoneCheckin.objects.get_or_create(
                        patient=patient,
                        milestone=milestone,
                        defaults={
                            "sent_at": patient.surgery_date + timedelta(days=milestone.day)
                            if milestone.day <= days_post_op
                            else None,
                            "completed_at": checkin_status["completed_at"],
                            "skipped": not checkin_status["completed"] and milestone.day < days_post_op - 7,
                            "responses": {},
                        },
                    )

    def _create_conversations(self, patients: list[Patient]):
        """Create realistic conversations for patients."""
        self.stdout.write("\nCreating conversations...")

        # Define realistic conversations for specific patients
        # Format: patient_index: [(role, content, agent_type), ...]
        conversation_data = {
            # Robert Chen - CABG, Day 2, Red (critical escalation)
            0: [
                (
                    "user",
                    "Hi, I had CABG surgery 2 days ago and I'm having severe chest pain, about 8 out of 10. It radiates to my left arm and I'm sweating. Is this normal?",
                    "",
                ),
                (
                    "assistant",
                    "Robert, I'm very concerned about your symptoms. Severe chest pain with radiation to your arm and sweating is not typical for day 2 post-CABG. I'm escalating this immediately to your care team. Please have someone stay with you while we get a nurse on the line.",
                    "nurse_triage",
                ),
                ("user", "Okay, my wife is here with me. Should I call 911?", ""),
                (
                    "assistant",
                    "Given the severity of your symptoms, please call 911 now. I'm also immediately escalating this to your surgical team and having them coordinate with the emergency department so they're expecting you. Your wife should stay with you. Do not wait - call 911 first, then we'll coordinate your care.",
                    "nurse_triage",
                ),
            ],
            # Patricia Williams - CABG, Day 5, Orange (urgent escalation)
            1: [
                (
                    "user",
                    "Hello, I'm Patricia. I had CABG 5 days ago and I'm feeling fluttering in my chest occasionally with some dizziness.",
                    "",
                ),
                (
                    "assistant",
                    "Hi Patricia, occasional palpitations can happen after heart surgery, but combined with dizziness, this needs evaluation. Are you checking your pulse when this happens?",
                    "nurse_triage",
                ),
                ("user", "Yes, it feels irregular when it happens. Maybe skipping a beat?", ""),
                (
                    "assistant",
                    "Thank you for that detail. Irregular heartbeats with dizziness post-CABG should be evaluated by your care team. I'm escalating this to your cardiologist. In the meantime, please rest and avoid strenuous activity. Someone will contact you within the hour.",
                    "nurse_triage",
                ),
                ("user", "Should I be worried?", ""),
                (
                    "assistant",
                    "It's understandable to be concerned, but many rhythm issues after surgery are manageable. The important thing is that we evaluate it promptly. Keep track of when these episodes occur and how long they last. Do you have a blood pressure monitor at home?",
                    "nurse_triage",
                ),
            ],
            # James Morrison - CABG, Day 3, Red (critical escalation - infection)
            2: [
                (
                    "user",
                    "Hi, this is James. My incision looks really red and warm, and there's some yellow discharge. I also have a fever of 101.8.",
                    "",
                ),
                (
                    "assistant",
                    "James, these are signs of a possible wound infection. The combination of redness, warmth, discharge, and fever needs immediate attention. I'm escalating this as critical - you need to be seen today.",
                    "nurse_triage",
                ),
                ("user", "Should I go to the ER or call my surgeon?", ""),
                (
                    "assistant",
                    "I'm connecting you directly with your care team right now. Given your symptoms, you need to be seen today. I'm escalating this to your surgeon and arranging for an urgent virtual visit or in-person evaluation within the next few hours. Please stay near your phone - a nurse will call you within 30 minutes. Do not wait until tomorrow.",
                    "nurse_triage",
                ),
            ],
            # Linda Rodriguez - CABG, Day 8, Yellow
            3: [
                (
                    "user",
                    "Hi, I'm Linda. Day 8 post-CABG. The chest pain is much better but I'm having trouble sleeping on my back still.",
                    "",
                ),
                (
                    "assistant",
                    "Hi Linda! Great to hear your pain is improving. Difficulty sleeping on your back is very common - many patients find side sleeping with a pillow supporting their chest more comfortable after the first week. Have you tried that?",
                    "care_coordinator",
                ),
                ("user", "I tried my side but felt like I was pulling on the incision.", ""),
                (
                    "assistant",
                    "That makes sense. Try placing a small pillow or rolled towel against your chest when side-lying to minimize pulling. You can also try sleeping in a recliner or with extra pillows to prop yourself at an angle. Most patients find sleep improves significantly by week 2-3.",
                    "care_coordinator",
                ),
                ("user", "When can I sleep normally again?", ""),
                (
                    "assistant",
                    "Most patients can return to their preferred sleeping position by 3-4 weeks post-surgery, though some still use chest support for comfort. Listen to your body - if a position causes discomfort, give it more time. How is your energy during the day?",
                    "care_coordinator",
                ),
            ],
            # Michael Thompson - CABG, Day 12, Yellow (routine escalation)
            4: [
                (
                    "user",
                    "Hello, I'm Michael. Quick question about my evening medications - should I take them with or without food?",
                    "",
                ),
                (
                    "assistant",
                    "Hi Michael! Most cardiac medications can be taken with or without food, but some are better absorbed with food. Which specific medication are you asking about?",
                    "care_coordinator",
                ),
                ("user", "The metoprolol and the aspirin.", ""),
                (
                    "assistant",
                    "Metoprolol can be taken either way, though some patients find taking it with food reduces any stomach upset. Aspirin is best taken with food to protect your stomach. Is there a specific reason you're concerned about the timing?",
                    "care_coordinator",
                ),
                ("user", "No, just want to make sure I'm doing it right. Also, when is my next appointment?", ""),
                (
                    "assistant",
                    "You're doing great by asking! Let me check your appointment schedule. I can see you have a virtual visit coming up. Would you like me to confirm the date and time for you?",
                    "care_coordinator",
                ),
            ],
            # David Lee - AVR, Day 4, Orange (urgent - elevated INR)
            16: [
                (
                    "user",
                    "Hi, this is David. I had aortic valve replacement 4 days ago. My INR came back at 4.2 and I had a nosebleed this morning. Also noticing more bruises on my arms.",
                    "",
                ),
                (
                    "assistant",
                    "David, an INR of 4.2 is above the typical target range of 2.0-3.0 for mechanical valves. Combined with the nosebleed and increased bruising, this needs attention. Have you had any other bleeding?",
                    "nurse_triage",
                ),
                ("user", "No other bleeding, but the bruises seem to appear easily.", ""),
                (
                    "assistant",
                    "That bruising is consistent with the elevated INR. I'm escalating this to your care team right now - a nurse will contact you within the hour to discuss adjusting your warfarin dose and whether you need your INR rechecked today. In the meantime, avoid activities that could cause injury and report any new bleeding immediately.",
                    "nurse_triage",
                ),
                ("user", "Should I skip today's warfarin dose?", ""),
                (
                    "assistant",
                    "Don't skip or change your dose until you speak with your care team. I'm having a nurse call you within the hour to review your INR trend and give you specific instructions. They may want you to come in for a recheck today. Please keep your phone nearby.",
                    "nurse_triage",
                ),
            ],
            # Jennifer White - AVR, Day 7, Orange
            17: [
                (
                    "user",
                    "Hello, I'm Jennifer. I hear a clicking sound in my chest since my valve replacement. It's keeping me awake at night.",
                    "",
                ),
                (
                    "assistant",
                    "Hi Jennifer! That clicking sound is your new mechanical valve - it's completely normal and expected. Many patients describe it as sounding like a watch ticking. It may be more noticeable at night when it's quiet.",
                    "care_coordinator",
                ),
                ("user", "Will it always be this loud?", ""),
                (
                    "assistant",
                    "Most patients find they adapt to the sound over time and it becomes less noticeable. Some find that using a white noise machine or fan at night helps. The valve sound is actually a good sign - it means your valve is working! Have you been able to check your pulse to see if it's regular?",
                    "care_coordinator",
                ),
                ("user", "Yes, my pulse feels regular. I also have questions about my warfarin diet.", ""),
                (
                    "assistant",
                    "Great that your pulse is regular! For warfarin and diet, the key is consistency rather than avoidance. Keep your vitamin K intake (green leafy vegetables) consistent week to week. Would you like me to connect you with our pharmacy specialist for detailed anticoagulation guidance?",
                    "care_coordinator",
                ),
            ],
            # Mark Nelson - Mitral Repair, Day 9, Orange (urgent)
            25: [
                (
                    "user",
                    "Hi, I'm Mark. Day 9 after mitral valve repair. My pain was getting better but now it's increasing again, about 6 out of 10. I also have chills and don't feel like eating.",
                    "",
                ),
                (
                    "assistant",
                    "Mark, increasing pain after initial improvement, combined with chills and loss of appetite, is concerning. This pattern can indicate an infection or other complication. I'm escalating this to your care team for evaluation today.",
                    "nurse_triage",
                ),
                ("user", "Should I check my temperature?", ""),
                (
                    "assistant",
                    "Yes, please check your temperature right away. If it's over 100.4°F, that's another sign we need to evaluate. Also check your incision for any increased redness, warmth, or drainage. How does the incision look compared to yesterday?",
                    "nurse_triage",
                ),
                ("user", "It looks about the same, maybe slightly more red at the top.", ""),
                (
                    "assistant",
                    "Please take your temperature now and let me know what it is. Given your symptoms, I'm escalating this to your care team for immediate evaluation. A nurse will contact you within 30 minutes to arrange either an urgent virtual visit or direct you to be seen in person today. Keep your phone nearby.",
                    "nurse_triage",
                ),
            ],
            # Jason Parker - PCI/Stent, Day 5, Yellow
            30: [
                (
                    "user",
                    "Hi, I'm Jason. Had a stent placed 5 days ago through my wrist. The insertion site is still sore and there's a bruise.",
                    "",
                ),
                (
                    "assistant",
                    "Hi Jason! Some soreness and bruising at the wrist insertion site is normal for several days after the procedure. Is the bruise getting larger or is there any active bleeding?",
                    "care_coordinator",
                ),
                ("user", "No bleeding, the bruise seems stable. Just tender to touch.", ""),
                (
                    "assistant",
                    "That sounds normal. The tenderness should gradually improve over the next week. Keep the site clean and dry. You can expect the bruising to change colors (purple to green to yellow) as it heals. Are you taking your dual antiplatelet medications as prescribed?",
                    "care_coordinator",
                ),
                ("user", "Yes, aspirin and clopidogrel every day. Any side effects I should watch for?", ""),
                (
                    "assistant",
                    "Good question! Watch for unusual bleeding (gums, nose, blood in urine/stool), severe bruising, or black/tarry stools. Also report any chest pain, shortness of breath, or allergic reactions like rash. Otherwise, you should be feeling back to normal activities soon!",
                    "care_coordinator",
                ),
            ],
            # Gary Morris - Pacemaker, Day 6, Green
            40: [
                (
                    "user",
                    "Hello, I'm Gary. Had a pacemaker put in 6 days ago. When can I raise my arm above my shoulder?",
                    "",
                ),
                (
                    "assistant",
                    "Hi Gary! You'll want to keep your arm on the pacemaker side below shoulder level for about 2 weeks to allow the leads to settle in properly. After that, you can gradually return to normal movement.",
                    "care_coordinator",
                ),
                ("user", "What about driving?", ""),
                (
                    "assistant",
                    "Most patients can return to driving about 1 week after pacemaker implantation, but you should confirm with your doctor first. The main concern is being able to react quickly and safely. Have you had your device check yet?",
                    "care_coordinator",
                ),
                ("user", "Not yet, they said it would be remote monitoring.", ""),
                (
                    "assistant",
                    "Yes, modern pacemakers can be monitored remotely! The device sends data to your care team automatically. You should receive a monitoring device for your home. Have they given you information about that yet?",
                    "care_coordinator",
                ),
            ],
            # Emily Cook - Maze Procedure, Day 19, Green
            45: [
                ("user", "Hi, I'm Emily. Had the Maze procedure 19 days ago for AFib. How do I know if it worked?", ""),
                (
                    "assistant",
                    "Hi Emily! The Maze procedure creates scar tissue to block abnormal electrical signals. Success is measured by staying in normal sinus rhythm. Have you noticed any irregular heartbeats or palpitations since the surgery?",
                    "care_coordinator",
                ),
                ("user", "I haven't felt any fluttering like I used to. My pulse feels regular.", ""),
                (
                    "assistant",
                    "That's a great sign! Many patients notice the difference right away. Your doctor will confirm with an EKG at your follow-up. Are you still taking the antiarrhythmic medications?",
                    "care_coordinator",
                ),
                ("user", "Yes, still taking them. When do they usually stop those?", ""),
                (
                    "assistant",
                    "Antiarrhythmic medications are typically continued for about 3 months post-procedure as the heart tissue heals and the scar lines mature. Your doctor will monitor your rhythm and decide when it's safe to discontinue. Any other questions about your recovery?",
                    "care_coordinator",
                ),
            ],
        }

        # Create conversations for patients with defined data
        for patient_idx, messages in conversation_data.items():
            if patient_idx >= len(patients):
                continue

            patient = patients[patient_idx]

            # Create conversation
            conv, _ = AgentConversation.objects.get_or_create(
                patient=patient,
                agent_type="supervisor",
                defaults={"status": "active"},
            )

            # Add messages
            for role, content, agent_type in messages:
                AgentMessage.objects.create(
                    conversation=conv,
                    role=role,
                    content=content,
                    agent_type=agent_type if role == "assistant" else "",
                    routing_decision=agent_type if role == "assistant" else "",
                )

        # Create additional conversations for remaining patients with varied templates
        remaining_patients = [p for i, p in enumerate(patients) if i not in conversation_data and p.surgery_date]

        for patient in remaining_patients:
            days_post = (date.today() - patient.surgery_date).days if patient.surgery_date else 0
            surgery_type = patient.surgery_type or "Cardiac Surgery"

            # Determine phase and create appropriate conversation
            if days_post < 7:
                messages = self._get_early_recovery_messages(patient, surgery_type, days_post)
            elif days_post < 21:
                messages = self._get_middle_recovery_messages(patient, surgery_type, days_post)
            else:
                messages = self._get_late_recovery_messages(patient, surgery_type, days_post)

            if messages:
                conv, _ = AgentConversation.objects.get_or_create(
                    patient=patient,
                    agent_type="supervisor",
                    defaults={"status": "active"},
                )

                for role, content, agent_type in messages:
                    AgentMessage.objects.create(
                        conversation=conv,
                        role=role,
                        content=content,
                        agent_type=agent_type if role == "assistant" else "",
                        routing_decision=agent_type if role == "assistant" else "",
                    )

    def _get_early_recovery_messages(self, patient: Patient, surgery_type: str, days_post: int) -> list:
        """Generate early recovery conversation messages."""
        name = patient.user.first_name

        early_templates = [
            [
                (
                    "user",
                    f"Hi, I'm {name}. I'm {days_post} days post-{surgery_type} and having trouble with pain management at night.",
                    "",
                ),
                (
                    "assistant",
                    f"Hi {name}! Nighttime pain is common as you settle down and notice discomfort more. Are you taking your pain medication on a schedule or only when the pain gets bad?",
                    "care_coordinator",
                ),
                ("user", "Only when it hurts. I don't want to take too many pills.", ""),
                (
                    "assistant",
                    "I understand your concern, but taking pain medication on a schedule for the first 1-2 weeks actually provides better control and helps you sleep and move around, which aids healing. Follow your prescription schedule - you can always taper down as you improve.",
                    "care_coordinator",
                ),
            ],
            [
                ("user", f"Hello, {name} here. Day {days_post} after {surgery_type}. When can I shower normally?", ""),
                (
                    "assistant",
                    f"Hi {name}! You can usually shower after 48 hours, but keep the water temperature moderate and avoid direct spray on your incision. Pat the incision dry gently - don't rub. Have you already started showering?",
                    "care_coordinator",
                ),
                ("user", "Yes, I've been showering but covering the incision with plastic wrap.", ""),
                (
                    "assistant",
                    "That's being cautious, which is good! After the first few days, you don't need the plastic wrap. Just let water run over the incision and pat it dry. Watch for any signs of infection like increasing redness or drainage.",
                    "care_coordinator",
                ),
            ],
            [
                (
                    "user",
                    f"Hi, this is {name}. I'm having trouble with constipation since my {surgery_type} {days_post} days ago.",
                    "",
                ),
                (
                    "assistant",
                    f"Hi {name}, this is very common after surgery due to anesthesia and pain medications. Are you drinking plenty of fluids and eating fiber?",
                    "care_coordinator",
                ),
                ("user", "I'm trying, but I don't have much appetite.", ""),
                (
                    "assistant",
                    "Small frequent meals can help. Also, your doctor may have prescribed a stool softener - make sure you're taking it. Walking helps too, even just short distances. If you haven't had a bowel movement by day 4-5, let me know and I'll connect you with your care team to discuss options.",
                    "care_coordinator",
                ),
            ],
        ]

        return random.choice(early_templates)

    def _get_middle_recovery_messages(self, patient: Patient, surgery_type: str, days_post: int) -> list:
        """Generate middle recovery conversation messages."""
        name = patient.user.first_name

        middle_templates = [
            [
                (
                    "user",
                    f"Hi {name} here. I'm {days_post} days post-{surgery_type} and wondering when I can start driving again?",
                    "",
                ),
                (
                    "assistant",
                    f"Hi {name}! Most patients can drive about 2-4 weeks after surgery, but you need to be off pain medication and able to turn the wheel and react quickly. Are you still taking pain meds?",
                    "care_coordinator",
                ),
                ("user", "Only Tylenol now, no more narcotics.", ""),
                (
                    "assistant",
                    "That's great progress! Tylenol is fine for driving. Make sure you can comfortably turn the wheel and perform an emergency stop. Start with short trips and see how you feel. Have you had your follow-up appointment yet?",
                    "care_coordinator",
                ),
            ],
            [
                (
                    "user",
                    f"Hello, I'm {name}. Day {days_post} after {surgery_type}. My incision is itching like crazy. Is that normal?",
                    "",
                ),
                (
                    "assistant",
                    f"Hi {name}! Itching is actually a good sign - it means the incision is healing and the nerves are regenerating. Try not to scratch it. You can apply a gentle moisturizer around (not directly on) the incision if the skin is dry.",
                    "care_coordinator",
                ),
                ("user", "It's driving me nuts! How long will this last?", ""),
                (
                    "assistant",
                    "It can last several weeks as the healing continues. Some patients find that cool compresses help. Just make sure the incision is fully closed before applying anything. Is there any redness or drainage, or just itching?",
                    "care_coordinator",
                ),
            ],
            [
                (
                    "user",
                    f"Hi, {name} here. I'm {days_post} days out from {surgery_type} and feeling more tired than I expected.",
                    "",
                ),
                (
                    "assistant",
                    f"Hi {name}, fatigue is very common and can last 4-8 weeks after cardiac surgery. Your body is using a lot of energy to heal. Are you getting enough rest but also doing some light activity like walking?",
                    "care_coordinator",
                ),
                ("user", "I'm walking about 10 minutes twice a day, but then I need a nap.", ""),
                (
                    "assistant",
                    "That sounds appropriate! Listen to your body - activity is good, but rest is equally important for healing. Gradually increase your walking time as your energy improves. Most patients see significant improvement by week 4-6.",
                    "care_coordinator",
                ),
            ],
        ]

        return random.choice(middle_templates)

    def _get_late_recovery_messages(self, patient: Patient, surgery_type: str, days_post: int) -> list:
        """Generate late recovery conversation messages."""
        name = patient.user.first_name

        late_templates = [
            [
                (
                    "user",
                    f"Hi {name} here. I'm {days_post} days post-{surgery_type} and feeling much better! When can I lift my grandkids again?",
                    "",
                ),
                (
                    "assistant",
                    f"Hi {name}, wonderful to hear you're feeling better! For lifting, most patients are cleared to lift 10-15 pounds by 6-8 weeks. How much do your grandkids weigh?",
                    "care_coordinator",
                ),
                ("user", "The little one is about 25 pounds.", ""),
                (
                    "assistant",
                    "You'll want to wait until your surgeon clears you for heavier lifting, typically around 8-12 weeks post-surgery. In the meantime, you can sit and have them climb into your lap, or hold them while sitting. Have you been cleared for any lifting yet?",
                    "care_coordinator",
                ),
            ],
            [
                (
                    "user",
                    f"Hello, I'm {name}. Day {days_post} after {surgery_type}. I'm back to work part-time and doing well. Question about travel.",
                    "",
                ),
                (
                    "assistant",
                    f"Hi {name}, great to hear you're back to work! Travel is generally fine by 4-6 weeks post-surgery. Are you planning a trip?",
                    "care_coordinator",
                ),
                ("user", "Yes, we want to visit family about 3 hours away by car.", ""),
                (
                    "assistant",
                    "A 3-hour car ride should be fine at {days_post} days! Stop every hour to walk around and stretch. Stay hydrated and wear compression stockings if you have them. Bring your medications and emergency contact information just in case.",
                    "care_coordinator",
                ),
            ],
            [
                (
                    "user",
                    f"Hi, {name} here. I'm almost {days_post} days post-{surgery_type} and wondering about exercise. Can I start jogging?",
                    "",
                ),
                (
                    "assistant",
                    f"Hi {name}! Before starting jogging, you should be cleared by your doctor and ideally complete cardiac rehabilitation. Are you in cardiac rehab or have you been cleared for exercise?",
                    "care_coordinator",
                ),
                ("user", "I finished cardiac rehab last week. They said I could gradually increase activity.", ""),
                (
                    "assistant",
                    "Perfect! Start with brisk walking and gradually work up to light jogging. Listen to your body - you should be able to maintain a conversation while exercising. Stop if you feel chest pain, unusual shortness of breath, or dizziness. Build up slowly over several weeks.",
                    "care_coordinator",
                ),
            ],
        ]

        return random.choice(late_templates)

    def _create_escalations(self, patients: list[Patient], clinicians: list[Clinician]):
        """Create escalations for critical/urgent patients."""
        self.stdout.write("\nCreating escalations...")

        escalation_data = [
            # Critical escalations (2)
            {
                "patient_idx": 0,  # Robert Chen - CABG, Day 2, Red
                "severity": "critical",
                "reason": "Patient reporting severe chest pain (8/10) with radiation to left arm, shortness of breath, and diaphoresis. Possible cardiac event.",
                "status": "acknowledged",
            },
            {
                "patient_idx": 2,  # James Morrison - CABG, Day 3, Red
                "severity": "critical",
                "reason": "Wound infection suspected: incision site red, warm, with purulent drainage. Fever 101.8°F.",
                "status": "acknowledged",
            },
            # Urgent escalations (3)
            {
                "patient_idx": 1,  # Patricia Williams - CABG, Day 5, Orange
                "severity": "urgent",
                "reason": "Patient experiencing palpitations with occasional dizziness. Heart rate irregular during home monitoring.",
                "status": "pending",
            },
            {
                "patient_idx": 16,  # David Lee - AVR, Day 4, Orange
                "severity": "urgent",
                "reason": "INR 4.2 (elevated), patient reports nosebleed this morning and unusual bruising on arms.",
                "status": "acknowledged",
            },
            {
                "patient_idx": 25,  # Mark Nelson - Mitral, Day 9, Orange
                "severity": "urgent",
                "reason": "Pain increasing rather than decreasing (now 6/10). Patient also reports chills and loss of appetite.",
                "status": "pending",
            },
            # Routine escalations (5)
            {
                "patient_idx": 4,  # Michael Thompson - CABG, Day 12, Yellow
                "severity": "routine",
                "reason": "Questions about medication timing - patient unsure whether to take evening dose with or without food.",
                "status": "pending",
            },
            {
                "patient_idx": 17,  # Jennifer White - AVR, Day 7, Orange
                "severity": "routine",
                "reason": "Request for clarification on activity restrictions - specifically wants to know about golf restrictions.",
                "status": "acknowledged",
            },
            {
                "patient_idx": 30,  # Jason Parker - PCI, Day 5, Yellow
                "severity": "routine",
                "reason": "Patient reporting mild rash after starting clopidogrel. No other symptoms, asking if this is expected.",
                "status": "pending",
            },
            {
                "patient_idx": 6,  # William Anderson - CABG, Day 6, Yellow
                "severity": "routine",
                "reason": "Scheduling question - patient needs to reschedule day 10 virtual visit due to conflict.",
                "status": "acknowledged",
            },
            {
                "patient_idx": 41,  # Gary Morris - Pacemaker, Day 6, Green
                "severity": "routine",
                "reason": "Device check question - patient wants to confirm next remote monitoring session is scheduled.",
                "status": "pending",
            },
        ]

        for esc in escalation_data:
            if esc["patient_idx"] < len(patients):
                patient = patients[esc["patient_idx"]]
                clinician = clinicians[esc["patient_idx"] % len(clinicians)]

                Escalation.objects.get_or_create(
                    patient=patient,
                    reason=esc["reason"],
                    defaults={
                        "severity": esc["severity"],
                        "status": esc["status"],
                        "escalation_type": "clinical",
                        "conversation_summary": f"AI conversation with {patient.user.get_full_name()} escalated for clinician review.",
                        "assigned_to": clinician.user if esc["status"] != "pending" else None,
                        "acknowledged_at": timezone.now() if esc["status"] == "acknowledged" else None,
                    },
                )

    def _create_appointments(self, patients: list[Patient], clinicians: list[Clinician]):
        """Create virtual visit appointments for days 3, 10, 21."""
        self.stdout.write("\nCreating appointments...")

        appointment_count = 0
        for patient in patients:
            if not patient.surgery_date:
                continue

            days_post = (date.today() - patient.surgery_date).days
            clinician = clinicians[patient.id % len(clinicians)]

            # Create appointments based on where patient is in recovery
            milestones = [3, 10, 21]

            for milestone_day in milestones:
                if days_post >= milestone_day - 2:  # Appointment exists
                    # Determine status
                    if days_post > milestone_day + 2:
                        status = random.choice(["completed", "completed", "no_show"])
                    elif days_post >= milestone_day:
                        status = random.choice(["completed", "in_progress"])
                    else:
                        status = "scheduled"

                    appt_date = patient.surgery_date + timedelta(days=milestone_day)
                    appt_datetime = datetime.combine(appt_date, datetime.min.time()) + timedelta(hours=10)

                    Appointment.objects.get_or_create(
                        patient=patient,
                        clinician=clinician,
                        appointment_type="virtual_visit",
                        scheduled_start=appt_datetime,
                        defaults={
                            "status": status,
                            "scheduled_end": appt_datetime + timedelta(minutes=30),
                            "notes": f"Day {milestone_day} virtual visit milestone",
                            "virtual_visit_url": f"https://clintela.telehealth.io/visit/{patient.id}",
                        },
                    )
                    appointment_count += 1

        self.stdout.write(f"  Created {appointment_count} appointments")

    def _create_caregivers(self, patients: list[Patient]):
        """Create caregiver relationships for 15 patients."""
        self.stdout.write("\nCreating caregivers...")

        # Select 15 patients to have caregivers
        patients_with_caregivers = random.sample([p for p in patients if p.surgery_date], 15)

        caregiver_profiles = [
            ("Mary", "Chen", "spouse"),
            ("John", "Williams", "spouse"),
            ("Sarah", "Morrison", "child"),
            ("Carlos", "Rodriguez", "spouse"),
            ("Karen", "Thompson", "spouse"),
            ("Michael", "Davis", "child"),
            ("Linda", "Anderson", "spouse"),
            ("Richard", "Taylor", "spouse"),
            ("Patricia", "Wilson", "spouse"),
            ("Thomas", "Garcia", "child"),
            ("Susan", "Martinez", "spouse"),
            ("Robert", "Robinson", "spouse"),
            ("Jennifer", "Clark", "child"),
            ("David", "Hernandez", "spouse"),
            ("Barbara", "Lopez", "spouse"),
        ]

        for i, patient in enumerate(patients_with_caregivers):
            if i >= len(caregiver_profiles):
                break

            first_name, last_name, relationship = caregiver_profiles[i]

            # Create caregiver user
            cg_username = f"cg_{first_name.lower()}_{patient.id}"
            cg_user, created = User.objects.get_or_create(
                username=cg_username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": f"{cg_username}@caregiver.test",
                    "role": "caregiver",
                },
            )
            if created:
                cg_user.set_password("testpass123")
                cg_user.save()

            # Create caregiver profile
            caregiver, _ = Caregiver.objects.get_or_create(
                user=cg_user,
                defaults={
                    "relationship_type": relationship,
                    "is_verified": True,
                    "is_active": True,
                },
            )

            # Create invitation
            invitation, _ = CaregiverInvitation.objects.get_or_create(
                patient=patient,
                name=f"{first_name} {last_name}",
                defaults={
                    "relationship": relationship,
                    "status": "accepted",
                    "accepted_by": cg_user,
                    "accepted_at": timezone.now(),
                },
            )

            # Create relationship
            CaregiverRelationship.objects.get_or_create(
                caregiver=caregiver,
                patient=patient,
                defaults={
                    "relationship": relationship,
                    "is_active": True,
                    "accepted_at": timezone.now(),
                },
            )

            self.stdout.write(f"  Caregiver for {patient.user.first_name}: {first_name} ({relationship})")

    def _create_clinician_notes(self, patients: list[Patient], clinicians: list[Clinician]):
        """Create clinician notes for various patients."""
        self.stdout.write("\nCreating clinician notes...")

        note_templates = [
            {
                "type": "clinical_observation",
                "content": "Patient recovering well post-{surgery}. Incision healing appropriately. Pain well-controlled. Continue current plan.",
            },
            {
                "type": "follow_up",
                "content": "Follow-up visit scheduled. Patient reports continued improvement. No new concerns. Cleared for next phase of recovery.",
            },
            {
                "type": "care_plan_note",
                "content": "Care plan updated: Increased activity clearance granted. Patient educated on sternal precautions. Cardiac rehab referral submitted.",
            },
            {
                "type": "quick_note",
                "content": "Spoke with patient regarding {concern}. Reassured and provided guidance.",
            },
        ]

        # Create notes for ~25 patients
        patients_with_notes = random.sample([p for p in patients if p.surgery_date], 25)

        for patient in patients_with_notes:
            clinician = clinicians[patient.id % len(clinicians)]

            # 1-2 notes per patient
            num_notes = random.randint(1, 2)
            for _ in range(num_notes):
                template = random.choice(note_templates)
                concern = random.choice(
                    ["pain management", "activity restrictions", "medication questions", "wound care", "sleep issues"]
                )

                content = template["content"].format(
                    surgery=patient.surgery_type,
                    concern=concern,
                )

                ClinicianNote.objects.create(
                    patient=patient,
                    clinician=clinician,
                    content=content,
                    note_type=template["type"],
                )

    def _create_consent_records(self, patients: list[Patient]):
        """Create consent records for all patients."""
        self.stdout.write("\nCreating consent records...")

        consent_types = [
            "data_sharing_caregiver",
            "data_sharing_research",
            "communication_sms",
            "communication_email",
            "ai_interaction",
        ]

        for patient in patients:
            for consent_type in consent_types:
                ConsentRecord.objects.get_or_create(
                    patient=patient,
                    consent_type=consent_type,
                    granted=True,
                    granted_by=patient.user,
                )
