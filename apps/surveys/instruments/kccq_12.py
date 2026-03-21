"""KCCQ-12: Kansas City Cardiomyopathy Questionnaire (12-item)."""

from typing import Any

from apps.surveys.instruments import register
from apps.surveys.instruments.base import BaseInstrument
from apps.surveys.scoring import ScoringResult

KCCQ_LIKERT_5 = [
    {"value": 1, "label": "Extremely limited"},
    {"value": 2, "label": "Quite a bit limited"},
    {"value": 3, "label": "Moderately limited"},
    {"value": 4, "label": "Slightly limited"},
    {"value": 5, "label": "Not at all limited"},
]

KCCQ_FREQUENCY_5 = [
    {"value": 1, "label": "Every morning"},
    {"value": 2, "label": "3 or more times a week"},
    {"value": 3, "label": "1-2 times a week"},
    {"value": 4, "label": "Less than once a week"},
    {"value": 5, "label": "Never over the past 2 weeks"},
]

KCCQ_BOTHERED_5 = [
    {"value": 1, "label": "Extremely bothersome"},
    {"value": 2, "label": "Quite a bit bothersome"},
    {"value": 3, "label": "Moderately bothersome"},
    {"value": 4, "label": "Slightly bothersome"},
    {"value": 5, "label": "Not at all bothersome"},
]

KCCQ_QOL_5 = [
    {"value": 1, "label": "Not at all satisfied"},
    {"value": 2, "label": "Mostly dissatisfied"},
    {"value": 3, "label": "Somewhat satisfied"},
    {"value": 4, "label": "Mostly satisfied"},
    {"value": 5, "label": "Completely satisfied"},
]


@register
class KCCQ12(BaseInstrument):
    code = "kccq_12"
    name = "Kansas City Cardiomyopathy Questionnaire-12"
    version = "1.0"
    category = "cardiac"
    estimated_minutes = 8

    def get_questions(self) -> list[dict[str, Any]]:
        return [
            {
                "code": "pl_dressing",
                "domain": "physical_limitation",
                "order": 1,
                "text": "Heart failure limits your ability to dress yourself — how much?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_LIKERT_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "pl_showering",
                "domain": "physical_limitation",
                "order": 2,
                "text": "Heart failure limits your ability to shower or bathe — how much?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_LIKERT_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "pl_walking",
                "domain": "physical_limitation",
                "order": 3,
                "text": "Heart failure limits your ability to walk 1 block on level ground — how much?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_LIKERT_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "sf_frequency",
                "domain": "symptom_frequency",
                "order": 4,
                "text": "Over the past 2 weeks, how many times did you have swelling in your feet, ankles, or legs when you woke up in the morning?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_FREQUENCY_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "sf_fatigue",
                "domain": "symptom_frequency",
                "order": 5,
                "text": "Over the past 2 weeks, how much has fatigue limited your ability to do what you want?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_LIKERT_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "sf_shortness",
                "domain": "symptom_frequency",
                "order": 6,
                "text": "Over the past 2 weeks, how much has shortness of breath limited your ability to do what you want?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_LIKERT_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "sb_frequency",
                "domain": "symptom_burden",
                "order": 7,
                "text": "Over the past 2 weeks, how often have you been forced to sleep sitting up in a chair or with at least 3 pillows?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_FREQUENCY_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "sb_bother",
                "domain": "symptom_burden",
                "order": 8,
                "text": "Over the past 2 weeks, how much has swelling in your feet, ankles, or legs bothered you?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_BOTHERED_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "sl_social",
                "domain": "social_limitation",
                "order": 9,
                "text": "Heart failure limits your hobbies or recreational activities — how much?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_LIKERT_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "sl_intimacy",
                "domain": "social_limitation",
                "order": 10,
                "text": "Heart failure limits your intimate relationships — how much?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_LIKERT_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "ql_satisfaction",
                "domain": "quality_of_life",
                "order": 11,
                "text": "How satisfied are you with your current condition?",  # noqa: E501
                "question_type": "likert",
                "options": KCCQ_QOL_5,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "ql_discouraged",
                "domain": "quality_of_life",
                "order": 12,
                "text": "How much does heart failure affect your enjoyment of life?",  # noqa: E501
                "question_type": "likert",
                "options": [
                    {"value": 1, "label": "It has severely limited my enjoyment of life"},
                    {"value": 2, "label": "It has limited my enjoyment of life quite a bit"},
                    {"value": 3, "label": "It has moderately limited my enjoyment of life"},
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
        ]

    def score(self, answers: dict[str, Any]) -> ScoringResult:
        """KCCQ-12 scoring: each domain rescaled to 0-100, higher is better."""
        domains = {
            "physical_limitation": ["pl_dressing", "pl_showering", "pl_walking"],
            "symptom_frequency": ["sf_frequency", "sf_fatigue", "sf_shortness"],
            "symptom_burden": ["sb_frequency", "sb_bother"],
            "social_limitation": ["sl_social", "sl_intimacy"],
            "quality_of_life": ["ql_satisfaction", "ql_discouraged"],
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
                # Rescale from 1-5 to 0-100
                mean = sum(values) / len(values)
                domain_scores[domain] = round((mean - 1) * 25, 1)

        # Overall summary score is mean of all domains
        total = round(sum(domain_scores.values()) / len(domain_scores), 1) if domain_scores else 0.0

        # Interpretation
        if total >= 75:
            interpretation = "Good health status"
        elif total >= 50:
            interpretation = "Moderate limitation"
        elif total >= 25:
            interpretation = "Significant limitation"
        else:
            interpretation = "Severe limitation — needs attention"

        escalation_needed = total < 25
        severity = "urgent" if total < 25 else ""
        reason = f"KCCQ-12 score {total}/100 indicates severe limitation" if escalation_needed else ""

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
        return [
            "physical_limitation",
            "symptom_frequency",
            "symptom_burden",
            "social_limitation",
            "quality_of_life",
        ]

    def get_escalation_defaults(self) -> dict[str, Any]:
        return {
            "total": {"threshold": 25, "severity": "urgent", "type": "clinical"},
            "domains": {
                "physical_limitation": {"threshold": 20, "severity": "warning"},
            },
        }

    def get_display_config(self) -> dict[str, Any]:
        return {
            "mode": "grouped",
            "groups": [
                {"domain": "physical_limitation", "title": "Physical Limitations"},
                {"domain": "symptom_frequency", "title": "Symptom Frequency"},
                {"domain": "symptom_burden", "title": "Symptom Burden"},
                {"domain": "social_limitation", "title": "Social Limitations"},
                {"domain": "quality_of_life", "title": "Quality of Life"},
            ],
        }

    def get_change_alert_config(self) -> dict[str, Any] | None:
        return {"min_delta": 10, "direction": "decrease", "severity": "warning"}
