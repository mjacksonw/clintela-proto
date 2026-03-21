"""PROMIS Global Health-10: Patient-Reported Outcomes Measurement Information System."""

from typing import Any

from apps.surveys.instruments import register
from apps.surveys.instruments.base import BaseInstrument
from apps.surveys.scoring import ScoringResult

PROMIS_EXCELLENT_POOR = [
    {"value": 5, "label": "Excellent"},
    {"value": 4, "label": "Very good"},
    {"value": 3, "label": "Good"},
    {"value": 2, "label": "Fair"},
    {"value": 1, "label": "Poor"},
]

PROMIS_COMPLETELY_NOT = [
    {"value": 5, "label": "Completely"},
    {"value": 4, "label": "Mostly"},
    {"value": 3, "label": "Moderately"},
    {"value": 2, "label": "A little"},
    {"value": 1, "label": "Not at all"},
]

PROMIS_NEVER_ALWAYS = [
    {"value": 5, "label": "Never"},
    {"value": 4, "label": "Rarely"},
    {"value": 3, "label": "Sometimes"},
    {"value": 2, "label": "Often"},
    {"value": 1, "label": "Always"},
]


@register
class PROMISGlobal(BaseInstrument):
    code = "promis_global"
    name = "PROMIS Global Health-10"
    version = "1.0"
    category = "general"
    estimated_minutes = 5

    def get_questions(self) -> list[dict[str, Any]]:
        return [
            {
                "code": "general_health",
                "domain": "physical",
                "order": 1,
                "text": "In general, would you say your health is:",  # noqa: E501
                "question_type": "likert",
                "options": PROMIS_EXCELLENT_POOR,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "quality_life",
                "domain": "physical",
                "order": 2,
                "text": "In general, would you say your quality of life is:",  # noqa: E501
                "question_type": "likert",
                "options": PROMIS_EXCELLENT_POOR,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "physical_health",
                "domain": "physical",
                "order": 3,
                "text": "In general, how would you rate your physical health?",  # noqa: E501
                "question_type": "likert",
                "options": PROMIS_EXCELLENT_POOR,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "mental_health",
                "domain": "mental",
                "order": 4,
                "text": "In general, how would you rate your mental health, including your mood and your ability to think?",  # noqa: E501
                "question_type": "likert",
                "options": PROMIS_EXCELLENT_POOR,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "social_satisfaction",
                "domain": "mental",
                "order": 5,
                "text": "In general, how would you rate your satisfaction with your social activities and relationships?",  # noqa: E501
                "question_type": "likert",
                "options": PROMIS_EXCELLENT_POOR,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "daily_activities",
                "domain": "physical",
                "order": 6,
                "text": "To what extent are you able to carry out your everyday physical activities?",  # noqa: E501
                "question_type": "likert",
                "options": PROMIS_COMPLETELY_NOT,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "Such as walking, climbing stairs, carrying groceries, or moving a chair.",
            },
            {
                "code": "emotional_problems",
                "domain": "mental",
                "order": 7,
                "text": "In the past 7 days, how often have you been bothered by emotional problems such as feeling anxious, depressed, or irritable?",  # noqa: E501
                "question_type": "likert",
                "options": PROMIS_NEVER_ALWAYS,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "fatigue",
                "domain": "physical",
                "order": 8,
                "text": "In the past 7 days, how would you rate your fatigue on average?",  # noqa: E501
                "question_type": "likert",
                "options": [
                    {"value": 5, "label": "None"},
                    {"value": 4, "label": "Mild"},
                    {"value": 3, "label": "Moderate"},
                    {"value": 2, "label": "Severe"},
                    {"value": 1, "label": "Very severe"},
                ],
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "pain",
                "domain": "physical",
                "order": 9,
                "text": "In the past 7 days, how would you rate your pain on average?",  # noqa: E501
                "question_type": "numeric",
                "options": [],
                "min_value": 0,
                "max_value": 10,
                "min_label": "No pain",
                "max_label": "Worst pain imaginable",
                "required": True,
                "help_text": "",
            },
            {
                "code": "social_roles",
                "domain": "mental",
                "order": 10,
                "text": "In the past 7 days, to what extent has your physical health or emotional problems limited your usual social activities with family or friends?",  # noqa: E501
                "question_type": "likert",
                "options": PROMIS_COMPLETELY_NOT,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
        ]

    def score(self, answers: dict[str, Any]) -> ScoringResult:
        physical_codes = [
            "general_health",
            "quality_life",
            "physical_health",
            "daily_activities",
            "fatigue",
        ]
        mental_codes = [
            "mental_health",
            "social_satisfaction",
            "emotional_problems",
            "social_roles",
        ]

        raw_scores = {}
        physical_values = []
        mental_values = []

        for code in physical_codes:
            val = answers.get(code)
            if val is not None:
                val = int(val)
                raw_scores[code] = val
                physical_values.append(val)

        for code in mental_codes:
            val = answers.get(code)
            if val is not None:
                val = int(val)
                raw_scores[code] = val
                mental_values.append(val)

        # Pain is reverse scored (0-10 where 0=no pain, convert to 1-5 scale)
        pain_val = answers.get("pain")
        if pain_val is not None:
            pain_val = int(pain_val)
            raw_scores["pain"] = pain_val
            # Invert: 0 pain = 5, 10 pain = 1
            pain_rescaled = round(5 - (pain_val / 10 * 4))
            physical_values.append(max(1, pain_rescaled))

        # Calculate raw sums then convert to T-scores (simplified)
        physical_raw = sum(physical_values) if physical_values else 0
        mental_raw = sum(mental_values) if mental_values else 0

        # Simplified T-score approximation (actual PROMIS uses IRT lookup tables)
        # Raw sum range: 6-30 for physical (6 items), 4-20 for mental (4 items)
        physical_t = round(20 + physical_raw / (len(physical_values) * 5) * 40, 1) if physical_values else 0.0

        mental_t = round(20 + mental_raw / (len(mental_values) * 5) * 40, 1) if mental_values else 0.0

        domain_scores = {
            "physical": physical_t,
            "mental": mental_t,
        }

        total = round((physical_t + mental_t) / 2, 1)

        if total >= 50:
            interpretation = "Average or above-average health"
        elif total >= 40:
            interpretation = "Below average — some health concerns"
        elif total >= 30:
            interpretation = "Significant health concerns"
        else:
            interpretation = "Severe health concerns — needs attention"

        escalation_needed = total < 30
        return ScoringResult(
            total_score=total,
            domain_scores=domain_scores,
            raw_scores=raw_scores,
            interpretation=interpretation,
            escalation_needed=escalation_needed,
            escalation_severity="urgent" if escalation_needed else "",
            escalation_reason=f"PROMIS Global score {total} indicates severe health concerns"
            if escalation_needed
            else "",
        )

    def get_domains(self) -> list[str]:
        return ["physical", "mental"]

    def get_escalation_defaults(self) -> dict[str, Any]:
        return {"total": {"threshold": 30, "severity": "urgent", "type": "clinical"}}

    def get_display_config(self) -> dict[str, Any]:
        return {
            "mode": "grouped",
            "groups": [
                {"domain": "physical", "title": "Physical Health"},
                {"domain": "mental", "title": "Mental Health"},
            ],
        }

    def get_change_alert_config(self) -> dict[str, Any] | None:
        return {"min_delta": 5, "direction": "decrease", "severity": "warning"}
