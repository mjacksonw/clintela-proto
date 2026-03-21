"""AFEQT: Atrial Fibrillation Effect on Quality of Life."""

from typing import Any

from apps.surveys.instruments import register
from apps.surveys.instruments.base import BaseInstrument
from apps.surveys.scoring import ScoringResult

AFEQT_SCALE = [
    {"value": 1, "label": "Not at all"},
    {"value": 2, "label": "A little"},
    {"value": 3, "label": "Somewhat"},
    {"value": 4, "label": "A lot"},
    {"value": 5, "label": "Extremely"},
    {"value": 6, "label": "Activities avoided due to AF"},
    {"value": 7, "label": "Not applicable"},
]

AFEQT_BOTHER = [
    {"value": 1, "label": "Not at all bothered"},
    {"value": 2, "label": "A little bothered"},
    {"value": 3, "label": "Somewhat bothered"},
    {"value": 4, "label": "A lot bothered"},
    {"value": 5, "label": "Extremely bothered"},
]


@register
class AFEQT(BaseInstrument):
    code = "afeqt"
    name = "Atrial Fibrillation Effect on Quality of Life"
    version = "1.0"
    category = "cardiac"
    estimated_minutes = 6

    def get_questions(self) -> list[dict[str, Any]]:
        return [
            {
                "code": "symptoms_palpitations",
                "domain": "symptoms",
                "order": 1,
                "text": "During the past 4 weeks, how bothered have you been by heart racing or irregular heartbeat sensations?",  # noqa: E501
                "question_type": "likert",
                "options": AFEQT_BOTHER,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "symptoms_dizziness",
                "domain": "symptoms",
                "order": 2,
                "text": "During the past 4 weeks, how bothered have you been by dizziness or fainting?",  # noqa: E501
                "question_type": "likert",
                "options": AFEQT_BOTHER,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "symptoms_fatigue",
                "domain": "symptoms",
                "order": 3,
                "text": "During the past 4 weeks, how bothered have you been by fatigue or lack of energy?",  # noqa: E501
                "question_type": "likert",
                "options": AFEQT_BOTHER,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "symptoms_breath",
                "domain": "symptoms",
                "order": 4,
                "text": "During the past 4 weeks, how bothered have you been by shortness of breath with activity?",  # noqa: E501
                "question_type": "likert",
                "options": AFEQT_BOTHER,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "daily_walking",
                "domain": "daily_activities",
                "order": 5,
                "text": "During the past 4 weeks, how much has your AF limited you in taking a walk or going for a run?",  # noqa: E501
                "question_type": "likert",
                "options": AFEQT_SCALE[:6],
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "daily_chores",
                "domain": "daily_activities",
                "order": 6,
                "text": "During the past 4 weeks, how much has your AF limited you in doing household chores?",  # noqa: E501
                "question_type": "likert",
                "options": AFEQT_SCALE[:6],
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "daily_social",
                "domain": "daily_activities",
                "order": 7,
                "text": "During the past 4 weeks, how much has your AF limited you in seeing friends or family?",  # noqa: E501
                "question_type": "likert",
                "options": AFEQT_SCALE[:6],
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "concern_worry",
                "domain": "treatment_concern",
                "order": 8,
                "text": "During the past 4 weeks, how worried have you been about having a stroke?",  # noqa: E501
                "question_type": "likert",
                "options": AFEQT_BOTHER,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "concern_treatment",
                "domain": "treatment_concern",
                "order": 9,
                "text": "During the past 4 weeks, how worried have you been about the side effects of your AF treatment?",  # noqa: E501
                "question_type": "likert",
                "options": AFEQT_BOTHER,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "overall_satisfaction",
                "domain": "",
                "order": 10,
                "text": "Overall, in the past 4 weeks, how satisfied are you with the current management of your AF?",  # noqa: E501
                "question_type": "likert",
                "options": [
                    {"value": 1, "label": "Very dissatisfied"},
                    {"value": 2, "label": "Dissatisfied"},
                    {"value": 3, "label": "Somewhat satisfied"},
                    {"value": 4, "label": "Satisfied"},
                    {"value": 5, "label": "Very satisfied"},
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
            "symptoms": ["symptoms_palpitations", "symptoms_dizziness", "symptoms_fatigue", "symptoms_breath"],
            "daily_activities": ["daily_walking", "daily_chores", "daily_social"],
            "treatment_concern": ["concern_worry", "concern_treatment"],
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
                    # Skip "not applicable" (7) and "activities avoided" (6) for daily activities
                    if val <= 5:
                        values.append(val)
            if values:
                max_val = 5
                mean = sum(values) / len(values)
                # AFEQT: lower is better (less bothered), invert to 0-100 scale where higher = better
                domain_scores[domain] = round((1 - (mean - 1) / (max_val - 1)) * 100, 1)

        # Overall satisfaction (standalone)
        sat_val = answers.get("overall_satisfaction")
        if sat_val is not None:
            raw_scores["overall_satisfaction"] = int(sat_val)

        total = round(sum(domain_scores.values()) / len(domain_scores), 1) if domain_scores else 0.0

        if total >= 75:
            interpretation = "Minimal AF impact on quality of life"
        elif total >= 50:
            interpretation = "Moderate AF impact"
        elif total >= 25:
            interpretation = "Significant AF impact"
        else:
            interpretation = "Severe AF impact — needs attention"

        escalation_needed = total < 25
        return ScoringResult(
            total_score=total,
            domain_scores=domain_scores,
            raw_scores=raw_scores,
            interpretation=interpretation,
            escalation_needed=escalation_needed,
            escalation_severity="urgent" if escalation_needed else "",
            escalation_reason=f"AFEQT score {total}/100 indicates severe AF impact" if escalation_needed else "",
        )

    def get_domains(self) -> list[str]:
        return ["symptoms", "daily_activities", "treatment_concern"]

    def get_escalation_defaults(self) -> dict[str, Any]:
        return {"total": {"threshold": 25, "severity": "urgent", "type": "clinical"}}

    def get_display_config(self) -> dict[str, Any]:
        return {
            "mode": "grouped",
            "groups": [
                {"domain": "symptoms", "title": "Symptoms"},
                {"domain": "daily_activities", "title": "Daily Activities"},
                {"domain": "treatment_concern", "title": "Treatment Concerns"},
            ],
        }

    def get_change_alert_config(self) -> dict[str, Any] | None:
        return {"min_delta": 10, "direction": "decrease", "severity": "warning"}
