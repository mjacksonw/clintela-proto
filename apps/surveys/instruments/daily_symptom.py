"""Daily Symptom Check — quick post-surgical recovery check-in."""

from typing import Any

from apps.surveys.instruments import register
from apps.surveys.instruments.base import BaseInstrument
from apps.surveys.scoring import ScoringResult


@register
class DailySymptomCheck(BaseInstrument):
    code = "daily_symptom"
    name = "Daily Symptom Check"
    version = "1.0"
    category = "symptom_check"
    estimated_minutes = 2

    def get_questions(self) -> list[dict[str, Any]]:
        return [
            {
                "code": "pain",
                "domain": "physical",
                "order": 1,
                "text": "How would you rate your pain right now?",
                "question_type": "numeric",
                "options": [],
                "min_value": 0,
                "max_value": 10,
                "min_label": "No pain",
                "max_label": "Worst pain",
                "required": True,
                "help_text": "",
            },
            {
                "code": "swelling",
                "domain": "physical",
                "order": 2,
                "text": "Have you noticed any new or increased swelling?",
                "question_type": "likert",
                "options": [
                    {"value": 0, "label": "No swelling"},
                    {"value": 1, "label": "Mild swelling"},
                    {"value": 2, "label": "Moderate swelling"},
                    {"value": 3, "label": "Severe swelling"},
                ],
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "fever",
                "domain": "physical",
                "order": 3,
                "text": "Have you had a fever or felt feverish today?",
                "question_type": "yes_no",
                "options": [
                    {"value": 1, "label": "Yes"},
                    {"value": 0, "label": "No"},
                ],
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "A temperature of 100.4°F (38°C) or higher is a fever.",
            },
            {
                "code": "wound",
                "domain": "physical",
                "order": 4,
                "text": "How does your surgical wound look?",
                "question_type": "likert",
                "options": [
                    {"value": 0, "label": "Clean and healing well"},
                    {"value": 1, "label": "Slightly red or tender"},
                    {"value": 2, "label": "Red, warm, or draining"},
                    {"value": 3, "label": "Very red, swollen, or has discharge"},
                ],
                "min_value": None,
                "max_value": None,
                "min_label": "",
                "max_label": "",
                "required": True,
                "help_text": "",
            },
            {
                "code": "mood",
                "domain": "emotional",
                "order": 5,
                "text": "How are you feeling emotionally today?",
                "question_type": "likert",
                "options": [
                    {"value": 0, "label": "Good — feeling positive"},
                    {"value": 1, "label": "Okay — managing"},
                    {"value": 2, "label": "Struggling — feeling low"},
                    {"value": 3, "label": "Very down — need support"},
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
        pain = int(answers.get("pain", 0))
        swelling = int(answers.get("swelling", 0))
        fever = int(answers.get("fever", 0))
        wound = int(answers.get("wound", 0))
        mood = int(answers.get("mood", 0))

        # Physical domain: pain (0-10) + swelling (0-3) + fever (0-1)*3 + wound (0-3)
        physical_score = pain + swelling + (fever * 3) + wound
        emotional_score = mood

        # Total is weighted sum, max ~22
        total = physical_score + emotional_score

        # Determine interpretation and escalation
        escalation_needed = False
        severity = ""
        reason = ""

        if pain >= 8 or wound >= 3 or fever == 1:
            escalation_needed = True
            severity = "urgent"
            reasons = []
            if pain >= 8:
                reasons.append(f"severe pain ({pain}/10)")
            if wound >= 3:
                reasons.append("concerning wound appearance")
            if fever == 1:
                reasons.append("fever reported")
            reason = f"Daily symptom check flagged: {', '.join(reasons)}"
            interpretation = "Attention needed — your care team will review"
        elif total >= 10:
            interpretation = "Some concerns noted — monitoring closely"
        elif total >= 5:
            interpretation = "Mild symptoms — recovery is progressing"
        else:
            interpretation = "Looking good — recovery on track"

        return ScoringResult(
            total_score=total,
            domain_scores={
                "physical": physical_score,
                "emotional": emotional_score,
            },
            raw_scores={
                "pain": pain,
                "swelling": swelling,
                "fever": fever,
                "wound": wound,
                "mood": mood,
            },
            interpretation=interpretation,
            escalation_needed=escalation_needed,
            escalation_severity=severity,
            escalation_reason=reason,
        )

    def get_domains(self) -> list[str]:
        return ["physical", "emotional"]

    def get_escalation_defaults(self) -> dict[str, Any]:
        return {
            "total": {"threshold": 15, "severity": "urgent", "type": "clinical"},
        }

    def get_change_alert_config(self) -> dict[str, Any] | None:
        return {"min_delta": 5, "direction": "increase", "severity": "warning"}
