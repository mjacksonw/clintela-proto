"""Deterministic scoring engine for survey instruments."""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScoringResult:
    total_score: float
    domain_scores: dict[str, float]
    raw_scores: dict[str, Any]
    interpretation: str
    escalation_needed: bool
    escalation_severity: str = ""
    escalation_reason: str = ""


class ScoringEngine:
    """Scores survey instances using registered instrument logic."""

    @staticmethod
    def score_instance(instance) -> ScoringResult | None:
        """Score a completed survey instance.

        Args:
            instance: SurveyInstance with answers loaded

        Returns:
            ScoringResult or None if instrument not found
        """
        from apps.surveys.instruments import registry

        instrument_cls = registry.get(instance.instrument.code)
        if instrument_cls is None:
            logger.warning(
                "Instrument %s not found in registry, skipping scoring",
                instance.instrument.code,
            )
            return None

        instrument = instrument_cls()

        # Build answers dict from SurveyAnswer records
        answers = {}
        for answer in instance.answers.select_related("question").all():
            answers[answer.question.code] = answer.value

        return instrument.score(answers)

    @staticmethod
    def check_escalation(instance, scoring_result: ScoringResult) -> bool:
        """Check if scoring result warrants an escalation.

        Uses assignment's escalation_config, falling back to instrument defaults.

        Args:
            instance: SurveyInstance
            scoring_result: ScoringResult from scoring

        Returns:
            True if escalation was created
        """
        if not scoring_result.escalation_needed:
            return False

        config = instance.assignment.escalation_config
        if not config:
            # Fall back to instrument defaults
            from apps.surveys.instruments import registry

            instrument_cls = registry.get(instance.instrument.code)
            if instrument_cls:
                config = instrument_cls().get_escalation_defaults()

        # Check total score threshold
        total_config = config.get("total", {})
        threshold = total_config.get("threshold")

        if threshold is not None and scoring_result.total_score >= threshold:
            return True

        # Check domain score thresholds
        domains_config = config.get("domains", {})
        for domain, domain_conf in domains_config.items():
            domain_threshold = domain_conf.get("threshold")
            domain_score = scoring_result.domain_scores.get(domain)
            if domain_threshold is not None and domain_score is not None and domain_score >= domain_threshold:
                return True

        return False
