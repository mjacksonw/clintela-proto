"""Management command to seed enhanced cardiac surgery pathways."""

from django.core.management.base import BaseCommand

from apps.pathways.models import ClinicalPathway, PathwayMilestone


class Command(BaseCommand):
    """Seed database with enhanced cardiac surgery pathways for development."""

    help = "Create enhanced cardiac surgery pathways with day 3/10/21 virtual visits"

    def handle(self, *args, **options):
        """Create enhanced cardiac pathways."""
        self.stdout.write("Creating enhanced cardiac surgery pathways...")

        # CABG Pathway (60 days) with virtual visits at days 3, 10, 21
        cabg_pathway, _ = ClinicalPathway.objects.get_or_create(
            name="CABG Recovery",
            surgery_type="CABG",
            defaults={
                "description": "Complete recovery pathway for Coronary Artery Bypass Graft surgery "
                "with virtual visit milestones",
                "duration_days": 60,
                "is_active": True,
            },
        )

        cabg_milestones = [
            {
                "day": 1,
                "phase": "early",
                "title": "ICU Recovery",
                "description": "First 24 hours after CABG - critical monitoring phase",
                "expected_symptoms": [
                    "chest tube discomfort",
                    "sore throat from intubation",
                    "grogginess from anesthesia",
                    "mild chest tightness",
                ],
                "activities": ["breathing exercises every hour", "leg exercises in bed", "sit up with assistance"],
                "red_flags": [
                    "chest pain >6/10",
                    "difficulty breathing",
                    "irregular heartbeat",
                    "fever >101°F",
                    "bleeding from incision",
                ],
                "check_in_questions": [
                    "How is your breathing?",
                    "Are you doing your breathing exercises?",
                    "Any chest pain or tightness?",
                    "Rate your pain on a scale of 1-10",
                ],
            },
            {
                "day": 3,
                "phase": "early",
                "title": "Virtual Visit #1 - Early Recovery Assessment",
                "description": "Day 3 virtual visit: pain management, incision check, initial mobility evaluation",
                "expected_symptoms": [
                    "pain 3-5/10 with movement",
                    "fatigue",
                    "appetite changes",
                    "sleep disruption",
                    "mood changes",
                ],
                "activities": ["short walks to bathroom", "breathing exercises", "sternal precautions", "light meals"],
                "red_flags": [
                    "pain increasing instead of decreasing",
                    "incision redness spreading",
                    "drainage or pus from incision",
                    "fever >100.4°F",
                    "chest pain at rest",
                ],
                "check_in_questions": [
                    "How is your pain on a scale of 1-10?",
                    "Are you able to walk to the bathroom?",
                    "How does your incision look?",
                    "Are you eating and drinking normally?",
                    "Any concerns about your recovery so far?",
                ],
            },
            {
                "day": 7,
                "phase": "early",
                "title": "First Week Milestone",
                "description": "One week post-CABG: assessing wound healing and initial recovery progress",
                "expected_symptoms": ["pain 2-4/10", "fatigue improving", "sternal soreness", "mood fluctuations"],
                "activities": [
                    "walks around house",
                    "light household tasks",
                    "continue breathing exercises",
                    "shower with incision protection",
                ],
                "red_flags": ["worsening chest pain", "signs of infection", "swelling in legs", "shortness of breath"],
                "check_in_questions": [
                    "How is your energy level compared to day 3?",
                    "Are you walking more each day?",
                    "Any new symptoms or concerns?",
                    "How are you sleeping?",
                ],
            },
            {
                "day": 10,
                "phase": "middle",
                "title": "Virtual Visit #2 - Wound & Medication Review",
                "description": "Day 10 virtual visit: wound healing assessment, "
                "medication adherence, activity tolerance",
                "expected_symptoms": [
                    "pain 1-3/10",
                    "improving energy",
                    "possible medication side effects",
                    "itching at incision as it heals",
                ],
                "activities": [
                    "daily walks 5-10 minutes",
                    "light activities",
                    "sternal precautions still apply",
                    "normal daily routine resuming",
                ],
                "red_flags": [
                    "wound not healing",
                    "medication side effects severe",
                    "chest discomfort with activity",
                    "dizziness or palpitations",
                ],
                "check_in_questions": [
                    "How is your incision healing?",
                    "Are you taking your medications as prescribed?",
                    "Any side effects from medications?",
                    "How long can you walk before tiring?",
                    "Any chest discomfort with activity?",
                ],
            },
            {
                "day": 14,
                "phase": "middle",
                "title": "Two Week Check-In",
                "description": "Two weeks post-CABG: cardiac rehab preparation and activity clearance",
                "expected_symptoms": [
                    "minimal pain",
                    "steadily improving energy",
                    "normalizing sleep",
                    "sternal healing well",
                ],
                "activities": [
                    "prepare for cardiac rehab",
                    "increase walking duration",
                    "light household tasks OK",
                    "stairs if needed",
                ],
                "red_flags": [
                    "any new chest pain",
                    "signs of wound infection",
                    "extreme fatigue",
                    "irregular heartbeat",
                ],
                "check_in_questions": [
                    "Are you ready to start cardiac rehab?",
                    "How far can you walk now?",
                    "Any concerns about your heart?",
                    "How is your mood?",
                ],
            },
            {
                "day": 21,
                "phase": "middle",
                "title": "Virtual Visit #3 - Cardiac Rehab Progress",
                "description": "Day 21 virtual visit: cardiac rehab progress review, driving readiness assessment",
                "expected_symptoms": [
                    "pain minimal or none",
                    "good energy most days",
                    "sleep normalized",
                    "mood improving",
                ],
                "activities": [
                    "active in cardiac rehab",
                    "walking 15-20 minutes",
                    "light driving if cleared",
                    "returning to light work",
                ],
                "red_flags": [
                    "chest pain during rehab",
                    "excessive fatigue",
                    "dizziness during activity",
                    "shortness of breath",
                ],
                "check_in_questions": [
                    "How is cardiac rehab going?",
                    "Are you cleared to drive?",
                    "How is your activity tolerance?",
                    "Any concerns about returning to work?",
                    "How are your energy levels?",
                ],
            },
            {
                "day": 30,
                "phase": "late",
                "title": "One Month Milestone",
                "description": "One month post-CABG: driving clearance, return to work planning",
                "expected_symptoms": ["minimal to no pain", "good energy", "normal activities resuming"],
                "activities": [
                    "driving if cleared by surgeon",
                    "regular cardiac rehab",
                    "return to work part-time",
                    "light exercise",
                ],
                "red_flags": ["any new chest pain", "unusual fatigue", "swelling in legs"],
                "check_in_questions": [
                    "Are you back to driving?",
                    "How is your return to work going?",
                    "Any activity restrictions still bothering you?",
                    "How is cardiac rehab progressing?",
                ],
            },
            {
                "day": 60,
                "phase": "late",
                "title": "Recovery Complete",
                "description": "Two months post-CABG: full recovery assessment",
                "expected_symptoms": ["no pain", "normal energy", "fully healed incision"],
                "activities": [
                    "normal activities",
                    "regular exercise",
                    "full return to work",
                    "continued cardiac rehab",
                ],
                "red_flags": ["any cardiac symptoms", "chest pain with exertion", "unusual shortness of breath"],
                "check_in_questions": [
                    "How do you feel overall?",
                    "Are you back to your normal routine?",
                    "Any lingering concerns?",
                    "How has your recovery been overall?",
                ],
            },
        ]

        for m in cabg_milestones:
            PathwayMilestone.objects.get_or_create(
                pathway=cabg_pathway,
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

        self.stdout.write(self.style.SUCCESS(f"Created CABG pathway with {len(cabg_milestones)} milestones"))

        # Aortic Valve Replacement Pathway (90 days)
        avr_pathway, _ = ClinicalPathway.objects.get_or_create(
            name="Aortic Valve Replacement Recovery",
            surgery_type="Aortic Valve Replacement",
            defaults={
                "description": "Recovery pathway for aortic valve replacement with anticoagulation monitoring",
                "duration_days": 90,
                "is_active": True,
            },
        )

        avr_milestones = [
            {
                "day": 1,
                "phase": "early",
                "title": "Immediate Post-Op",
                "description": "First 24 hours after valve replacement",
                "expected_symptoms": ["chest discomfort", "sore throat", "fatigue", "grogginess"],
                "activities": ["ICU monitoring", "breathing exercises", "leg exercises", "rest"],
                "red_flags": ["severe chest pain", "irregular heartbeat", "breathing difficulty", "bleeding"],
                "check_in_questions": [
                    "How is your breathing?",
                    "Any chest discomfort?",
                    "Are you doing your exercises?",
                ],
            },
            {
                "day": 3,
                "phase": "early",
                "title": "Virtual Visit #1 - Early Assessment",
                "description": "Pain control, incision check, initial INR discussion",
                "expected_symptoms": ["pain 3-5/10", "fatigue", "appetite changes"],
                "activities": ["short walks", "breathing exercises", "sternal precautions"],
                "red_flags": ["increasing pain", "incision infection signs", "fever"],
                "check_in_questions": [
                    "Rate your pain 1-10",
                    "How is your incision?",
                    "Any bleeding or bruising?",
                    "Questions about warfarin?",
                ],
            },
            {
                "day": 7,
                "phase": "early",
                "title": "First Week",
                "description": "Wound healing and anticoagulation monitoring",
                "expected_symptoms": ["pain 2-4/10", "improving energy", "sternal soreness"],
                "activities": ["walking around house", "light activities", "INR check"],
                "red_flags": ["excessive bruising", "bleeding", "chest pain"],
                "check_in_questions": ["Any unusual bruising?", "How is your energy?", "INR results?"],
            },
            {
                "day": 10,
                "phase": "middle",
                "title": "Virtual Visit #2 - Anticoagulation Review",
                "description": "Warfarin/INR management, activity tolerance",
                "expected_symptoms": ["pain 1-3/10", "improving daily", "possible medication side effects"],
                "activities": ["daily walks", "normal routine resuming", "continue INR monitoring"],
                "red_flags": ["bleeding gums", "blood in urine", "severe bruising"],
                "check_in_questions": [
                    "Latest INR result?",
                    "Any bleeding concerns?",
                    "How is walking tolerance?",
                    "Diet consistent with warfarin?",
                ],
            },
            {
                "day": 14,
                "phase": "middle",
                "title": "Two Week Check-In",
                "description": "Cardiac rehab preparation, valve click awareness",
                "expected_symptoms": ["minimal pain", "mechanical valve click normal", "steady improvement"],
                "activities": ["prepare for cardiac rehab", "increased walking", "normal light activities"],
                "red_flags": ["new valve sounds", "dizziness", "palpitations"],
                "check_in_questions": ["Do you hear your valve click?", "Any dizziness?", "Ready for cardiac rehab?"],
            },
            {
                "day": 21,
                "phase": "middle",
                "title": "Virtual Visit #3 - Progress & Activity",
                "description": "Cardiac rehab progress, driving and activity clearance",
                "expected_symptoms": ["pain minimal", "good energy", "stable INR"],
                "activities": ["cardiac rehab active", "walking 15-20 min", "light driving if cleared"],
                "red_flags": ["chest pain with activity", "shortness of breath", "irregular heartbeat"],
                "check_in_questions": [
                    "How is cardiac rehab?",
                    "Latest INR stable?",
                    "Cleared for driving?",
                    "Any concerns with valve?",
                ],
            },
            {
                "day": 30,
                "phase": "late",
                "title": "One Month",
                "description": "Return to normal activities, ongoing anticoagulation",
                "expected_symptoms": ["no pain", "normal energy", "comfortable with valve"],
                "activities": ["driving", "work return", "regular exercise"],
                "red_flags": ["any cardiac symptoms", "bleeding issues"],
                "check_in_questions": [
                    "Back to normal routine?",
                    "INR management going well?",
                    "Any side effects from warfarin?",
                ],
            },
            {
                "day": 60,
                "phase": "late",
                "title": "Two Month Review",
                "description": "Continued recovery with anticoagulation management",
                "expected_symptoms": ["fully recovered", "stable anticoagulation"],
                "activities": ["normal life", "cardiac rehab", "ongoing INR monitoring"],
                "red_flags": ["bleeding complications", "cardiac symptoms"],
                "check_in_questions": ["How is overall recovery?", "Anticoagulation stable?", "Any concerns?"],
            },
            {
                "day": 90,
                "phase": "late",
                "title": "Recovery Complete",
                "description": "Full recovery, established on lifelong anticoagulation if mechanical valve",
                "expected_symptoms": ["fully healed", "stable on anticoagulation"],
                "activities": ["all normal activities", "established anticoag routine"],
                "red_flags": ["any new symptoms"],
                "check_in_questions": [
                    "Comfortable with valve?",
                    "Anticoagulation routine established?",
                    "Overall satisfaction with recovery?",
                ],
            },
        ]

        for m in avr_milestones:
            PathwayMilestone.objects.get_or_create(
                pathway=avr_pathway,
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
            self.style.SUCCESS(f"Created Aortic Valve Replacement pathway with {len(avr_milestones)} milestones")
        )

        # Mitral Valve Repair/Replacement Pathway (75 days)
        mitral_pathway, _ = ClinicalPathway.objects.get_or_create(
            name="Mitral Valve Repair/Replacement Recovery",
            surgery_type="Mitral Valve Repair",
            defaults={
                "description": "Recovery pathway for mitral valve procedures",
                "duration_days": 75,
                "is_active": True,
            },
        )

        # Also create for replacement
        mitral_replacement_pathway, _ = ClinicalPathway.objects.get_or_create(
            name="Mitral Valve Replacement Recovery",
            surgery_type="Mitral Valve Replacement",
            defaults={
                "description": "Recovery pathway for mitral valve replacement",
                "duration_days": 75,
                "is_active": True,
            },
        )

        mitral_milestones = [
            {
                "day": 1,
                "phase": "early",
                "title": "Immediate Post-Op",
                "description": "First 24 hours after mitral valve procedure",
                "expected_symptoms": ["chest discomfort", "sore throat", "fatigue"],
                "activities": ["ICU monitoring", "breathing exercises", "rest"],
                "red_flags": ["severe chest pain", "breathing difficulty", "bleeding"],
                "check_in_questions": ["How is your breathing?", "Any chest pain?", "Comfortable?"],
            },
            {
                "day": 3,
                "phase": "early",
                "title": "Virtual Visit #1",
                "description": "Pain, incision, and initial recovery assessment",
                "expected_symptoms": ["pain 3-5/10", "fatigue", "appetite changes"],
                "activities": ["short walks", "breathing exercises", "sternal precautions"],
                "red_flags": ["increasing pain", "incision issues", "fever"],
                "check_in_questions": ["Pain level?", "Incision appearance?", "Walking OK?", "Eating normally?"],
            },
            {
                "day": 7,
                "phase": "early",
                "title": "First Week",
                "description": "Recovery progress and wound healing",
                "expected_symptoms": ["pain 2-4/10", "improving energy", "sternal soreness"],
                "activities": ["house walking", "light tasks", "shower protection"],
                "red_flags": ["worsening symptoms", "infection signs"],
                "check_in_questions": ["Energy improving?", "Walking more?", "Any new symptoms?"],
            },
            {
                "day": 10,
                "phase": "middle",
                "title": "Virtual Visit #2",
                "description": "Wound healing and medication review",
                "expected_symptoms": ["pain 1-3/10", "improving daily", "possible med side effects"],
                "activities": ["daily walks", "light activities", "routine resuming"],
                "red_flags": ["wound issues", "medication problems", "chest discomfort"],
                "check_in_questions": ["Incision healing?", "Medications OK?", "Activity tolerance?", "Side effects?"],
            },
            {
                "day": 21,
                "phase": "middle",
                "title": "Virtual Visit #3",
                "description": "Activity progression and cardiac rehab readiness",
                "expected_symptoms": ["minimal pain", "good energy", "healing well"],
                "activities": ["cardiac rehab", "walking 15+ min", "light driving"],
                "red_flags": ["chest pain with activity", "palpitations", "shortness of breath"],
                "check_in_questions": [
                    "Cardiac rehab going well?",
                    "Cleared to drive?",
                    "Activity tolerance good?",
                    "Any heart rhythm concerns?",
                ],
            },
            {
                "day": 30,
                "phase": "late",
                "title": "One Month",
                "description": "Return to activities",
                "expected_symptoms": ["no pain", "normal energy"],
                "activities": ["driving", "work return", "cardiac rehab"],
                "red_flags": ["any cardiac symptoms"],
                "check_in_questions": ["Back to normal?", "Cardiac rehab progress?", "Any concerns?"],
            },
            {
                "day": 75,
                "phase": "late",
                "title": "Recovery Complete",
                "description": "Full recovery from mitral valve procedure",
                "expected_symptoms": ["fully healed", "normal"],
                "activities": ["all normal activities"],
                "red_flags": ["new symptoms"],
                "check_in_questions": ["Fully recovered?", "Satisfied with outcome?", "Any lingering issues?"],
            },
        ]

        for m in mitral_milestones:
            for pathway in [mitral_pathway, mitral_replacement_pathway]:
                PathwayMilestone.objects.get_or_create(
                    pathway=pathway,
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
            self.style.SUCCESS(f"Created Mitral Valve pathways with {len(mitral_milestones)} milestones each")
        )

        # PCI/Stent Pathway (30 days) - shorter recovery
        pci_pathway, _ = ClinicalPathway.objects.get_or_create(
            name="PCI with Stent Recovery",
            surgery_type="PCI with Stent",
            defaults={
                "description": "Recovery pathway for percutaneous coronary intervention with stent placement",
                "duration_days": 30,
                "is_active": True,
            },
        )

        pci_milestones = [
            {
                "day": 1,
                "phase": "early",
                "title": "Immediate Post-Procedure",
                "description": "First 24 hours after PCI/stent",
                "expected_symptoms": ["groin/wrist site tenderness", "mild chest discomfort", "fatigue"],
                "activities": ["rest", "light walking", "monitor insertion site"],
                "red_flags": ["severe chest pain", "bleeding from insertion site", "swelling at site", "fever"],
                "check_in_questions": ["How is your insertion site?", "Any chest pain?", "Bleeding or swelling?"],
            },
            {
                "day": 3,
                "phase": "early",
                "title": "Virtual Visit #1",
                "description": "Insertion site check, medication review",
                "expected_symptoms": ["minimal site discomfort", "improving energy"],
                "activities": ["light walking", "normal light activities"],
                "red_flags": ["site infection", "chest pain", "bleeding"],
                "check_in_questions": [
                    "Insertion site healing?",
                    "Taking dual antiplatelet meds?",
                    "Any bleeding or bruising?",
                    "Activity level?",
                ],
            },
            {
                "day": 7,
                "phase": "early",
                "title": "First Week",
                "description": "Activity progression",
                "expected_symptoms": ["minimal discomfort", "good energy"],
                "activities": ["walking", "light exercise", "normal routine"],
                "red_flags": ["chest pain", "shortness of breath"],
                "check_in_questions": ["How is your energy?", "Back to normal activities?", "Any concerns?"],
            },
            {
                "day": 10,
                "phase": "middle",
                "title": "Virtual Visit #2",
                "description": "Medication adherence and activity clearance",
                "expected_symptoms": ["no pain", "normal energy"],
                "activities": ["regular walking", "return to work", "driving"],
                "red_flags": ["chest discomfort", "medication side effects"],
                "check_in_questions": [
                    "Taking aspirin and clopidogrel?",
                    "Any side effects?",
                    "Cleared for work?",
                    "Activity unrestricted?",
                ],
            },
            {
                "day": 21,
                "phase": "middle",
                "title": "Virtual Visit #3",
                "description": "Final check before full activity clearance",
                "expected_symptoms": ["fully recovered", "no symptoms"],
                "activities": ["all normal activities", "exercise"],
                "red_flags": ["any cardiac symptoms"],
                "check_in_questions": [
                    "Fully recovered?",
                    "Back to all activities?",
                    "Medication questions?",
                    "Any concerns before discharge from pathway?",
                ],
            },
            {
                "day": 30,
                "phase": "late",
                "title": "Recovery Complete",
                "description": "Full recovery from PCI/stent",
                "expected_symptoms": ["normal", "no limitations"],
                "activities": ["all activities unrestricted"],
                "red_flags": ["new symptoms"],
                "check_in_questions": ["Fully recovered?", "Continuing dual antiplatelet therapy?", "Any concerns?"],
            },
        ]

        for m in pci_milestones:
            PathwayMilestone.objects.get_or_create(
                pathway=pci_pathway,
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

        self.stdout.write(self.style.SUCCESS(f"Created PCI/Stent pathway with {len(pci_milestones)} milestones"))

        # Pacemaker/ICD Pathway (14 days)
        pacemaker_pathway, _ = ClinicalPathway.objects.get_or_create(
            name="Pacemaker/ICD Implantation Recovery",
            surgery_type="Pacemaker/ICD",
            defaults={
                "description": "Recovery pathway for pacemaker or ICD implantation",
                "duration_days": 14,
                "is_active": True,
            },
        )

        pacemaker_milestones = [
            {
                "day": 1,
                "phase": "early",
                "title": "Immediate Post-Op",
                "description": "First 24 hours after device implantation",
                "expected_symptoms": ["incision discomfort", "soreness near device", "fatigue"],
                "activities": ["arm restriction", "light walking", "rest"],
                "red_flags": ["incision bleeding", "swelling at site", "fever", "severe pain"],
                "check_in_questions": ["How is your incision?", "Any swelling?", "Keeping arm restricted?"],
            },
            {
                "day": 3,
                "phase": "early",
                "title": "Virtual Visit #1",
                "description": "Incision check and activity guidance",
                "expected_symptoms": ["minimal discomfort", "improving"],
                "activities": ["light activities", "arm still restricted"],
                "red_flags": ["infection signs", "device concerns"],
                "check_in_questions": [
                    "Incision healing well?",
                    "Following arm restrictions?",
                    "Any device concerns?",
                    "Activity level?",
                ],
            },
            {
                "day": 7,
                "phase": "middle",
                "title": "One Week",
                "description": "Activity progression review",
                "expected_symptoms": ["minimal pain", "good energy"],
                "activities": ["increased activities", "still no heavy lifting"],
                "red_flags": ["chest pain", "dizziness", "palpitations"],
                "check_in_questions": ["Activity increasing?", "Still limiting arm movement?", "Any dizziness?"],
            },
            {
                "day": 14,
                "phase": "late",
                "title": "Recovery Complete",
                "description": "Full recovery, device check scheduled",
                "expected_symptoms": ["fully healed", "no restrictions"],
                "activities": ["all normal activities", "device check"],
                "red_flags": ["device malfunction signs", "new symptoms"],
                "check_in_questions": [
                    "Fully recovered?",
                    "Device check scheduled?",
                    "Any device concerns?",
                    "Comfortable with device?",
                ],
            },
        ]

        for m in pacemaker_milestones:
            PathwayMilestone.objects.get_or_create(
                pathway=pacemaker_pathway,
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
            self.style.SUCCESS(f"Created Pacemaker/ICD pathway with {len(pacemaker_milestones)} milestones")
        )

        # Maze Procedure Pathway (45 days)
        maze_pathway, _ = ClinicalPathway.objects.get_or_create(
            name="Maze Procedure Recovery",
            surgery_type="Maze Procedure",
            defaults={
                "description": "Recovery pathway for maze procedure (AFib treatment)",
                "duration_days": 45,
                "is_active": True,
            },
        )

        maze_milestones = [
            {
                "day": 1,
                "phase": "early",
                "title": "Immediate Post-Op",
                "description": "First 24 hours after maze procedure",
                "expected_symptoms": ["chest discomfort", "fatigue", "sore throat"],
                "activities": ["ICU monitoring", "breathing exercises", "rest"],
                "red_flags": ["severe chest pain", "irregular heartbeat", "breathing difficulty"],
                "check_in_questions": ["How is your breathing?", "Any chest pain?", "Heart rhythm regular?"],
            },
            {
                "day": 3,
                "phase": "early",
                "title": "Virtual Visit #1",
                "description": "Early recovery and rhythm assessment",
                "expected_symptoms": ["pain 3-5/10", "fatigue", "appetite changes"],
                "activities": ["short walks", "breathing exercises", "sternal precautions"],
                "red_flags": ["irregular heartbeat", "increasing pain", "fever"],
                "check_in_questions": [
                    "Pain level?",
                    "Heart rhythm regular?",
                    "Any palpitations?",
                    "Taking antiarrhythmics as prescribed?",
                ],
            },
            {
                "day": 7,
                "phase": "early",
                "title": "First Week",
                "description": "Rhythm stability and wound healing",
                "expected_symptoms": ["pain 2-4/10", "improving energy"],
                "activities": ["walking", "light activities"],
                "red_flags": ["AFib recurrence", "wound infection", "palpitations"],
                "check_in_questions": ["Heart rhythm stable?", "Energy improving?", "Any AFib symptoms?"],
            },
            {
                "day": 10,
                "phase": "middle",
                "title": "Virtual Visit #2",
                "description": "Rhythm monitoring and medication review",
                "expected_symptoms": ["pain 1-3/10", "good energy"],
                "activities": ["daily walks", "normal routine resuming"],
                "red_flags": ["irregular rhythm", "medication side effects"],
                "check_in_questions": [
                    "Still in normal rhythm?",
                    "Medications OK?",
                    "Activity tolerance?",
                    "Any AFib symptoms?",
                ],
            },
            {
                "day": 21,
                "phase": "middle",
                "title": "Virtual Visit #3",
                "description": "Long-term rhythm success assessment",
                "expected_symptoms": ["minimal pain", "normal energy", "stable rhythm"],
                "activities": ["cardiac rehab", "regular activities"],
                "red_flags": ["AFib recurrence", "chest pain"],
                "check_in_questions": [
                    "Still in normal sinus rhythm?",
                    "Cardiac rehab going well?",
                    "Any AFib symptoms?",
                    "Happy with procedure outcome?",
                ],
            },
            {
                "day": 45,
                "phase": "late",
                "title": "Recovery Complete",
                "description": "Full recovery with successful rhythm control",
                "expected_symptoms": ["fully recovered", "stable rhythm"],
                "activities": ["all normal activities"],
                "red_flags": ["AFib recurrence"],
                "check_in_questions": ["Still in normal rhythm?", "Satisfied with outcome?", "Any concerns?"],
            },
        ]

        for m in maze_milestones:
            PathwayMilestone.objects.get_or_create(
                pathway=maze_pathway,
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

        self.stdout.write(self.style.SUCCESS(f"Created Maze Procedure pathway with {len(maze_milestones)} milestones"))

        self.stdout.write(self.style.SUCCESS("\nAll enhanced cardiac pathways created successfully!"))
