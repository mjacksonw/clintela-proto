"""
Curated question bank for cardiac recovery check-ins.

Each question has:
- code: unique identifier
- category: one of the 8 categories
- text: patient-facing question text
- response_type: widget type
- options: for multiple_choice questions
- follow_up_rules: rules that trigger conversational follow-up
- priority: 1=highest (asked first when tied)
"""

CARDIAC_QUESTIONS = [
    # --- Pain ---
    {
        "code": "pain_level",
        "category": "pain",
        "text": "How's your pain right now?",
        "response_type": "scale_1_10",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "gte",
                "value": 7,
                "message": ("That sounds like a lot of pain. Can you describe where it hurts and what it feels like?"),
            },
        ],
        "priority": 1,
    },
    {
        "code": "pain_change",
        "category": "pain",
        "text": "Compared to yesterday, is your pain better, the same, or worse?",
        "response_type": "multiple_choice",
        "options": [
            {"value": "better", "label": "Better"},
            {"value": "same", "label": "About the same"},
            {"value": "worse", "label": "Worse"},
        ],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "worse",
                "message": (
                    "I'm sorry to hear your pain is worse. "
                    "Is there anything specific that makes it worse, "
                    "like moving or breathing?"
                ),
            },
        ],
        "priority": 3,
    },
    {
        "code": "pain_medication_effective",
        "category": "pain",
        "text": "Is your pain medication helping?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "no",
                "message": (
                    "That's important to know. Are you taking it as prescribed, "
                    "and about how long does the relief last?"
                ),
            },
        ],
        "priority": 2,
    },
    {
        "code": "chest_pain",
        "category": "pain",
        "text": "Have you had any chest pain or pressure today?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "yes",
                "message": (
                    "Please describe the chest pain. "
                    "Is it sharp, dull, or pressure-like? "
                    "Does it come and go or stay constant?"
                ),
            },
        ],
        "priority": 1,
    },
    # --- Sleep ---
    {
        "code": "sleep_quality",
        "category": "sleep",
        "text": "How did you sleep last night?",
        "response_type": "multiple_choice",
        "options": [
            {"value": "well", "label": "Slept well"},
            {"value": "woke_few", "label": "Woke up a few times"},
            {"value": "hardly", "label": "Hardly slept"},
        ],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "hardly",
                "message": (
                    "I'm sorry you had a rough night. What kept you up? Was it pain, anxiety, or something else?"
                ),
            },
        ],
        "priority": 1,
    },
    {
        "code": "sleep_position",
        "category": "sleep",
        "text": "Are you able to find a comfortable sleeping position?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "no",
                "message": (
                    "Finding comfort after surgery can be tough. "
                    "Are you sleeping elevated? "
                    "Sometimes extra pillows behind your back can help."
                ),
            },
        ],
        "priority": 3,
    },
    {
        "code": "sleep_hours",
        "category": "sleep",
        "text": "About how many hours did you sleep last night?",
        "response_type": "scale_1_10",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "lte",
                "value": 3,
                "message": (
                    "That's very little sleep. Your body needs rest to heal. "
                    "What do you think is keeping you from sleeping?"
                ),
            },
        ],
        "priority": 4,
    },
    # --- Bowel Function ---
    {
        "code": "bowel_movement",
        "category": "bowel",
        "text": "Have you been able to pass gas or have a bowel movement since yesterday?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "no",
                "message": "That's worth keeping an eye on. Are you feeling any bloating or nausea?",
            },
        ],
        "priority": 1,
    },
    {
        "code": "appetite",
        "category": "bowel",
        "text": "How's your appetite today?",
        "response_type": "multiple_choice",
        "options": [
            {"value": "good", "label": "Good, eating normally"},
            {"value": "reduced", "label": "Eating less than usual"},
            {"value": "none", "label": "Not hungry at all"},
        ],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "none",
                "message": "Loss of appetite can happen after surgery. Are you at least able to keep fluids down?",
            },
        ],
        "priority": 2,
    },
    {
        "code": "nausea",
        "category": "bowel",
        "text": "Have you experienced any nausea or vomiting today?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "yes",
                "message": (
                    "Is the nausea constant or does it come and go? "
                    "Have you been able to keep any food or liquids down?"
                ),
            },
        ],
        "priority": 2,
    },
    # --- Energy ---
    {
        "code": "energy_level",
        "category": "energy",
        "text": "How's your energy today?",
        "response_type": "scale_1_5",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "lte",
                "value": 1,
                "message": (
                    "Very low energy after surgery can be normal, "
                    "but let's make sure you're staying hydrated "
                    "and eating when you can."
                ),
            },
        ],
        "priority": 1,
    },
    {
        "code": "fatigue_daily_activities",
        "category": "energy",
        "text": "Are you able to do basic daily activities like eating, bathing, and getting dressed?",
        "response_type": "multiple_choice",
        "options": [
            {"value": "yes_independently", "label": "Yes, on my own"},
            {"value": "yes_with_help", "label": "Yes, with some help"},
            {"value": "no", "label": "Having trouble with them"},
        ],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "no",
                "message": "That sounds difficult. What activities are hardest for you right now?",
            },
        ],
        "priority": 2,
    },
    {
        "code": "dizziness",
        "category": "energy",
        "text": "Have you felt dizzy or lightheaded when standing up?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "yes",
                "message": (
                    "Dizziness when standing can mean a few things. "
                    "Are you drinking enough water? "
                    "Does it pass after a moment or does it linger?"
                ),
            },
        ],
        "priority": 2,
    },
    # --- Medication ---
    {
        "code": "medication_taken",
        "category": "medication",
        "text": "Have you been able to take all your medications as prescribed today?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "no",
                "message": (
                    "Which medications did you miss, and what got in the way? Sometimes we can work out easier timing."
                ),
            },
        ],
        "priority": 1,
    },
    {
        "code": "medication_side_effects",
        "category": "medication",
        "text": "Are you having any side effects from your medications?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "yes",
                "message": (
                    "What are you experiencing? "
                    "Knowing the specific side effects helps us "
                    "figure out the best next step."
                ),
            },
        ],
        "priority": 2,
    },
    {
        "code": "medication_confusion",
        "category": "medication",
        "text": "Do you have any questions or confusion about your medications?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "yes",
                "message": (
                    "Of course, what's unclear? I can help explain dosing, timing, or what each medication does."
                ),
            },
        ],
        "priority": 2,
    },
    # --- Mood ---
    {
        "code": "mood_today",
        "category": "mood",
        "text": "How are you feeling emotionally today?",
        "response_type": "multiple_choice",
        "options": [
            {"value": "good", "label": "Pretty good"},
            {"value": "okay", "label": "Okay"},
            {"value": "down", "label": "Feeling down"},
            {"value": "anxious", "label": "Anxious or worried"},
        ],
        "follow_up_rules": [
            {
                "operator": "in",
                "value": ["down", "anxious"],
                "message": "Recovery can be emotionally tough. Would you like to talk about what's on your mind?",
            },
        ],
        "priority": 1,
    },
    {
        "code": "loneliness",
        "category": "mood",
        "text": "Have you felt lonely or isolated during your recovery?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "yes",
                "message": (
                    "I hear you. Recovering at home can feel isolating. "
                    "Have you been able to talk to family or friends recently?"
                ),
            },
        ],
        "priority": 3,
    },
    {
        "code": "worry_recovery",
        "category": "mood",
        "text": "On a scale of 1-5, how worried are you about your recovery?",
        "response_type": "scale_1_5",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "gte",
                "value": 4,
                "message": "It's understandable to feel worried. What concerns you most right now?",
            },
        ],
        "priority": 2,
    },
    # --- Mobility ---
    {
        "code": "walking",
        "category": "mobility",
        "text": "Were you able to take a short walk today?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {"operator": "eq", "value": "no", "message": "What got in the way? Pain, fatigue, or something else?"},
        ],
        "priority": 1,
    },
    {
        "code": "mobility_compared",
        "category": "mobility",
        "text": "Compared to a few days ago, is moving around easier or harder?",
        "response_type": "multiple_choice",
        "options": [
            {"value": "easier", "label": "Easier"},
            {"value": "same", "label": "About the same"},
            {"value": "harder", "label": "Harder"},
        ],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "harder",
                "message": "I'm sorry it's getting harder. Is it a specific area that's more difficult, or overall?",
            },
        ],
        "priority": 2,
    },
    {
        "code": "swelling_legs",
        "category": "mobility",
        "text": "Have you noticed any swelling in your legs or ankles?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "yes",
                "message": "Is the swelling in one leg or both? And has it gotten worse since yesterday?",
            },
        ],
        "priority": 1,
    },
    # --- Wound Care ---
    {
        "code": "wound_appearance",
        "category": "wound",
        "text": "How does your incision site look today?",
        "response_type": "multiple_choice",
        "options": [
            {"value": "normal", "label": "Looks normal"},
            {"value": "red", "label": "A bit red or swollen"},
            {"value": "drainage", "label": "Some drainage or oozing"},
            {"value": "opening", "label": "Opening or separating"},
        ],
        "follow_up_rules": [
            {
                "operator": "in",
                "value": ["drainage", "opening"],
                "message": (
                    "That needs attention. "
                    "Can you describe the color and amount of drainage? "
                    "Is there any unusual smell?"
                ),
            },
        ],
        "priority": 1,
    },
    {
        "code": "wound_pain",
        "category": "wound",
        "text": "Is there increasing pain, warmth, or tenderness around your incision?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "yes",
                "message": (
                    "Increasing pain or warmth around the incision "
                    "could be a sign of infection. "
                    "When did you first notice this change?"
                ),
            },
        ],
        "priority": 1,
    },
    {
        "code": "fever",
        "category": "wound",
        "text": "Have you had a fever or chills today?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "yes",
                "message": (
                    "Fever after surgery can be important. "
                    "Do you know what your temperature is? "
                    "Even a rough guess helps."
                ),
            },
        ],
        "priority": 1,
    },
    # --- Additional cardiac-specific ---
    {
        "code": "shortness_of_breath",
        "category": "pain",
        "text": "Have you experienced any shortness of breath today?",
        "response_type": "multiple_choice",
        "options": [
            {"value": "none", "label": "No, breathing is fine"},
            {"value": "with_activity", "label": "Only with activity"},
            {"value": "at_rest", "label": "Even at rest"},
        ],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "at_rest",
                "message": (
                    "Shortness of breath at rest is something we take seriously. "
                    "Is this new today, or has it been building over a few days?"
                ),
            },
        ],
        "priority": 1,
    },
    {
        "code": "weight_change",
        "category": "bowel",
        "text": "Have you noticed any sudden weight gain in the past day or two?",
        "response_type": "yes_no",
        "options": [],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "yes",
                "message": (
                    "Sudden weight gain can be a sign of fluid retention. "
                    "About how much weight have you gained, "
                    "and are you noticing any swelling?"
                ),
            },
        ],
        "priority": 2,
    },
    {
        "code": "fluid_intake",
        "category": "bowel",
        "text": "Are you drinking enough fluids today?",
        "response_type": "multiple_choice",
        "options": [
            {"value": "plenty", "label": "Yes, plenty"},
            {"value": "some", "label": "Some, but could do better"},
            {"value": "very_little", "label": "Very little"},
        ],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "very_little",
                "message": "Staying hydrated is really important for healing. What's making it hard to drink?",
            },
        ],
        "priority": 3,
    },
    {
        "code": "overall_feeling",
        "category": "energy",
        "text": "Overall, how are you feeling compared to yesterday?",
        "response_type": "multiple_choice",
        "options": [
            {"value": "better", "label": "Better"},
            {"value": "same", "label": "About the same"},
            {"value": "worse", "label": "Worse"},
        ],
        "follow_up_rules": [
            {
                "operator": "eq",
                "value": "worse",
                "message": "I'm sorry you're feeling worse. What's changed since yesterday?",
            },
        ],
        "priority": 1,
    },
]


def seed_question_bank():
    """Seed the CheckinQuestion table with the cardiac recovery question bank.

    Idempotent: updates existing questions by code, creates new ones.
    Returns (created_count, updated_count).
    """
    from apps.checkins.models import CheckinQuestion

    created = 0
    updated = 0

    for q_data in CARDIAC_QUESTIONS:
        _, was_created = CheckinQuestion.objects.update_or_create(
            code=q_data["code"],
            defaults={
                "category": q_data["category"],
                "text": q_data["text"],
                "response_type": q_data["response_type"],
                "options": q_data["options"],
                "follow_up_rules": q_data["follow_up_rules"],
                "priority": q_data["priority"],
                "is_active": True,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return created, updated
