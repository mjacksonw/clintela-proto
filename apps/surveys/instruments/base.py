"""Base classes for survey instruments."""

from abc import ABC, abstractmethod
from typing import Any

from apps.surveys.scoring import ScoringResult


class BaseInstrument(ABC):
    """Abstract base class for survey instruments.

    Each instrument defines its questions, scoring logic, display configuration,
    and escalation defaults. Instruments are registered via the @register decorator
    and seeded into the database via the seed_instruments management command.
    """

    code: str = ""
    name: str = ""
    version: str = "1.0"
    category: str = "general"
    estimated_minutes: int = 5

    @abstractmethod
    def get_questions(self) -> list[dict[str, Any]]:
        """Return list of question definitions.

        Each dict has keys: code, domain, order, text, question_type, options,
        min_value, max_value, min_label, max_label, required, help_text.
        """

    @abstractmethod
    def score(self, answers: dict[str, Any]) -> ScoringResult:
        """Score a set of answers.

        Args:
            answers: Dict mapping question code to answer value

        Returns:
            ScoringResult with scores, interpretation, and escalation info
        """

    def get_domains(self) -> list[str]:
        """Return list of scoring domains for this instrument."""
        return []

    def get_escalation_defaults(self) -> dict[str, Any]:
        """Return default escalation config for this instrument."""
        return {}

    def get_display_config(self) -> dict[str, Any]:
        """Return display configuration for the survey wizard.

        Returns:
            Dict with:
                mode: "single_page" or "grouped"
                groups: list of {"domain": str, "title": str} (for grouped mode)
        """
        return {"mode": "single_page"}

    def get_change_alert_config(self) -> dict[str, Any] | None:
        """Return config for score change alerts to clinicians.

        Returns:
            Dict with min_delta, direction, severity, or None to disable.
        """
        return None


class InstrumentRegistry:
    """Registry of available instrument classes."""

    def __init__(self):
        self._instruments: dict[str, type[BaseInstrument]] = {}

    def register(self, cls: type[BaseInstrument]):
        """Register an instrument class."""
        if not cls.code:
            raise ValueError(f"Instrument {cls.__name__} has no code")
        self._instruments[cls.code] = cls

    def get(self, code: str) -> type[BaseInstrument] | None:
        """Get instrument class by code."""
        return self._instruments.get(code)

    def all(self) -> dict[str, type[BaseInstrument]]:
        """Return all registered instruments."""
        return dict(self._instruments)
