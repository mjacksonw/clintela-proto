"""PHQ-2: Patient Health Questionnaire (2-item depression screen)."""

from typing import Any

from apps.surveys.instruments import register
from apps.surveys.instruments.base import BaseInstrument
from apps.surveys.scoring import ScoringResult


@register
class PHQ2(BaseInstrument):
    code = "phq_2"
    name = "Patient Health Questionnaire-2"
    version = "1.0"
    category = "mental_health"
    estimated_minutes = 2

    def get_questions(self) -> list[dict[str, Any]]:
        options = [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ]
        return [
            {
                "code": "interest",
                "domain": "",
                "order": 1,
                "text": "Over the last 2 weeks, how often have you been bothered by little interest or pleasure in doing things?",  # noqa: E501
                "question_type": "likert",
                "options": options,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "depressed",
                "domain": "",
                "order": 2,
                "text": "Over the last 2 weeks, how often have you been bothered by feeling down, depressed, or hopeless?",  # noqa: E501
                "question_type": "likert",
                "options": options,
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
        ]

    def score(self, answers: dict[str, Any]) -> ScoringResult:
        interest = int(answers.get("interest", 0))
        depressed = int(answers.get("depressed", 0))
        total = interest + depressed

        if total >= 3:
            interpretation = "Probable major depression — further evaluation recommended"
            escalation_needed = True
            severity = "urgent"
            reason = f"PHQ-2 score {total}/6 indicates probable major depression"
        elif total >= 2:
            interpretation = "Mild concerns — monitor closely"
            escalation_needed = False
            severity = ""
            reason = ""
        else:
            interpretation = "Minimal concerns"
            escalation_needed = False
            severity = ""
            reason = ""

        return ScoringResult(
            total_score=total,
            domain_scores={},
            raw_scores={"interest": interest, "depressed": depressed},
            interpretation=interpretation,
            escalation_needed=escalation_needed,
            escalation_severity=severity,
            escalation_reason=reason,
        )

    def get_escalation_defaults(self) -> dict[str, Any]:
        return {
            "total": {"threshold": 3, "severity": "urgent", "type": "clinical"},
        }

    def get_change_alert_config(self) -> dict[str, Any] | None:
        return {"min_delta": 2, "direction": "increase", "severity": "warning"}
