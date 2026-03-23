"""Tests for patient preference injection in agent prompts."""

from apps.agents.prompts import (
    build_care_coordinator_prompt,
    build_nurse_triage_prompt,
    build_safety_hardened_prompt,
    build_specialist_prompt,
)


class TestCareCoordinatorPreferences:
    """Test preference injection in care coordinator prompts."""

    def test_prompt_without_preferences(self):
        """Prompt without preferences has no WHO THIS PATIENT IS block."""
        result = build_care_coordinator_prompt(
            patient_context="Test patient",
            conversation_history="",
            message="How am I doing?",
        )
        assert "WHO THIS PATIENT IS" not in result
        assert "How am I doing?" in result

    def test_prompt_with_preferences(self):
        """Prompt with preferences includes sandboxed block."""
        result = build_care_coordinator_prompt(
            patient_context="Test patient",
            conversation_history="",
            message="How am I doing?",
            patient_preferences="Preferred name: Maria\nGoals: Walk again",
        )
        assert "WHO THIS PATIENT IS" in result
        assert "BEGIN PATIENT PREFERENCES" in result
        assert "END PATIENT PREFERENCES" in result
        assert "Maria" in result
        assert "Walk again" in result

    def test_prompt_with_empty_preferences(self):
        """Empty string preferences treated as no preferences."""
        result = build_care_coordinator_prompt(
            patient_context="Test patient",
            conversation_history="",
            message="Hello",
            patient_preferences="",
        )
        assert "WHO THIS PATIENT IS" not in result


class TestNurseTriagePreferences:
    """Test preference injection in nurse triage prompts."""

    def test_prompt_without_preferences(self):
        result = build_nurse_triage_prompt(
            surgery_type="CABG",
            surgery_date="2026-01-15",
            days_post_op=5,
            current_phase="active_recovery",
            medications=["aspirin"],
            allergies=[],
            pathway_context="",
            message="My chest hurts",
        )
        assert "WHO THIS PATIENT IS" not in result
        assert "CABG" in result

    def test_prompt_with_preferences(self):
        result = build_nurse_triage_prompt(
            surgery_type="CABG",
            surgery_date="2026-01-15",
            days_post_op=5,
            current_phase="active_recovery",
            medications=["aspirin"],
            allergies=[],
            pathway_context="",
            message="My chest hurts",
            patient_preferences="Lives alone, anxious about pain",
        )
        assert "WHO THIS PATIENT IS" in result
        assert "anxious about pain" in result


class TestSpecialistPreferences:
    """Test preference injection in specialist prompts."""

    def test_prompt_without_preferences(self):
        result = build_specialist_prompt(
            agent_type="cardiology",
            patient_context="Test patient",
            message="Question about meds",
        )
        assert "WHO THIS PATIENT IS" not in result

    def test_prompt_with_preferences(self):
        result = build_specialist_prompt(
            agent_type="cardiology",
            patient_context="Test patient",
            message="Question about meds",
            patient_preferences="Values: Independence, staying at home",
        )
        assert "WHO THIS PATIENT IS" in result
        assert "Independence" in result

    def test_unknown_specialist_type(self):
        """Unknown specialist type uses generic fallback instructions."""
        result = build_specialist_prompt(
            agent_type="dermatology",
            patient_context="Test patient",
            message="Skin question",
        )
        assert "dermatology" in result


class TestSafetyHardenedPrompt:
    """Test safety prompt wrapping."""

    def test_wraps_prompt_with_safety_prefix(self):
        result = build_safety_hardened_prompt(
            base_prompt="You are a helpful care coordinator.",
            patient_message="I feel dizzy",
        )
        assert "helpful care coordinator" in result
        assert "I feel dizzy" in result
        # Should contain the safety prefix content
        assert len(result) > len("You are a helpful care coordinator.I feel dizzy")
