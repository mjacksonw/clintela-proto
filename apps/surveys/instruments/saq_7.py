"""SAQ-7: Seattle Angina Questionnaire (7-item)."""

from typing import Any

from apps.surveys.instruments import register
from apps.surveys.instruments.base import BaseInstrument
from apps.surveys.scoring import ScoringResult

SAQ_FREQUENCY = [
    {"value": 1, "label": "4 or more times per day"},
    {"value": 2, "label": "1-3 times per day"},
    {"value": 3, "label": "3 or more times per week"},
    {"value": 4, "label": "1-2 times per week"},
    {"value": 5, "label": "Less than once a week"},
    {"value": 6, "label": "None over the past 4 weeks"},
]

SAQ_LIMITATION = [
    {"value": 1, "label": "Severely limited"},
    {"value": 2, "label": "Moderately limited"},
    {"value": 3, "label": "Somewhat limited"},
    {"value": 4, "label": "A little limited"},
    {"value": 5, "label": "Not limited at all"},
]


@register
class SAQ7(BaseInstrument):
    code = "saq_7"
    name = "Seattle Angina Questionnaire-7"
    version = "1.0"
    category = "cardiac"
    estimated_minutes = 5

    def get_questions(self) -> list[dict[str, Any]]:
        return [
            {
                "code": "pl_walking",
                "domain": "physical_limitation",
                "order": 1,
                "text": "Walking indoors on level ground — how much are you limited by chest pain, pressure, or angina?",  # noqa: E501
                "question_type": "likert",
                "options": SAQ_LIMITATION,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "pl_gardening",
                "domain": "physical_limitation",
                "order": 2,
                "text": "Gardening, vacuuming, or carrying groceries — how much are you limited?",  # noqa: E501
                "question_type": "likert",
                "options": SAQ_LIMITATION,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "pl_climbing",
                "domain": "physical_limitation",
                "order": 3,
                "text": "Climbing a hill or a flight of stairs without stopping — how much are you limited?",  # noqa: E501
                "question_type": "likert",
                "options": SAQ_LIMITATION,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "af_frequency",
                "domain": "angina_frequency",
                "order": 4,
                "text": "Over the past 4 weeks, on average, how many times have you had chest pain, pressure, or angina?",  # noqa: E501
                "question_type": "likert",
                "options": SAQ_FREQUENCY,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "af_nitro",
                "domain": "angina_frequency",
                "order": 5,
                "text": "Over the past 4 weeks, on average, how many times have you had to take nitroglycerin for chest pain?",  # noqa: E501
                "question_type": "likert",
                "options": SAQ_FREQUENCY,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "ql_enjoyment",
                "domain": "quality_of_life",
                "order": 6,
                "text": "How much does your chest pain, pressure, or angina interfere with your enjoyment of life?",  # noqa: E501
                "question_type": "likert",
                "options": [
                    {"value": 1, "label": "It has severely limited my enjoyment of life"},
                    {"value": 2, "label": "It has moderately limited my enjoyment of life"},
                    {"value": 3, "label": "It has somewhat limited my enjoyment of life"},
                    {"value": 4, "label": "It has slightly limited my enjoyment of life"},
                    {"value": 5, "label": "It has not limited my enjoyment of life at all"},
                ],
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "ql_worry",
                "domain": "quality_of_life",
                "order": 7,
                "text": "If you had to spend the rest of your life with your angina the way it is right now, how would you feel?",  # noqa: E501
                "question_type": "likert",
                "options": [
                    {"value": 1, "label": "Not at all satisfied"},
                    {"value": 2, "label": "Mostly dissatisfied"},
                    {"value": 3, "label": "Somewhat satisfied"},
                    {"value": 4, "label": "Mostly satisfied"},
                    {"value": 5, "label": "Completely satisfied"},
                ],
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
        ]

    def score(self, answers: dict[str, Any]) -> ScoringResult:
        domains = {
            "physical_limitation": ["pl_walking", "pl_gardening", "pl_climbing"],
            "angina_frequency": ["af_frequency", "af_nitro"],
            "quality_of_life": ["ql_enjoyment", "ql_worry"],
        }

        domain_scores = {}
        raw_scores = {}

        for domain, codes in domains.items():
            values = []
            for code in codes:
                val = answers.get(code)
                if val is not None:
                    val = int(val)
                    raw_scores[code] = val
                    values.append(val)
            if values:
                mean = sum(values) / len(values)
                max_val = 6 if domain == "angina_frequency" else 5
                domain_scores[domain] = round((mean - 1) / (max_val - 1) * 100, 1)

        total = round(sum(domain_scores.values()) / len(domain_scores), 1) if domain_scores else 0.0

        if total >= 75:
            interpretation = "Minimal angina burden"
        elif total >= 50:
            interpretation = "Moderate angina burden"
        elif total >= 25:
            interpretation = "Significant angina burden"
        else:
            interpretation = "Severe angina burden — needs attention"

        escalation_needed = total < 25
        severity = "urgent" if escalation_needed else ""
        reason = f"SAQ-7 score {total}/100 indicates severe angina burden" if escalation_needed else ""

        return ScoringResult(
            total_score=total,
            domain_scores=domain_scores,
            raw_scores=raw_scores,
            interpretation=interpretation,
            escalation_needed=escalation_needed,
            escalation_severity=severity,
            escalation_reason=reason,
        )

    def get_domains(self) -> list[str]:
        return ["physical_limitation", "angina_frequency", "quality_of_life"]

    def get_escalation_defaults(self) -> dict[str, Any]:
        return {"total": {"threshold": 25, "severity": "urgent", "type": "clinical"}}

    def get_display_config(self) -> dict[str, Any]:
        return {
            "mode": "grouped",
            "groups": [
                {"domain": "physical_limitation", "title": "Physical Limitations"},
                {"domain": "angina_frequency", "title": "Angina Frequency"},
                {"domain": "quality_of_life", "title": "Quality of Life"},
            ],
        }

    def get_change_alert_config(self) -> dict[str, Any] | None:
        return {"min_delta": 10, "direction": "decrease", "severity": "warning"}
