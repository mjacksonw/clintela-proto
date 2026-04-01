"""Tests for apps.agents.personas — persona registry and helpers."""

from apps.agents.personas import (
    PERSONA_REGISTRY,
    PROCEDURE_BACKSTORIES,
    Persona,
    build_persona_prompt,
    get_persona,
    get_procedure_backstory,
)

EXPECTED_PERSONA_IDS = {"maria", "james", "linda", "tony", "priya", "robert", "diane"}

REQUIRED_FIELDS = (
    "id",
    "name",
    "age",
    "background",
    "procedure",
    "months_post_op",
    "therapeutic_role",
    "personality_traits",
    "speaking_style",
    "system_prompt_template",
    "weekly_prompt",
    "avatar_color",
    "avatar_color_dark",
    "avatar_initials",
    "base_response_probability",
    "example_phrases",
)


class TestPersonaRegistry:
    def test_all_personas_defined(self):
        """PERSONA_REGISTRY has 7 entries."""
        assert len(PERSONA_REGISTRY) == 7

    def test_persona_fields_complete(self):
        """Each persona has all required fields (non-empty)."""
        for pid, persona in PERSONA_REGISTRY.items():
            for field in REQUIRED_FIELDS:
                value = getattr(persona, field)
                assert value, f"Persona {pid!r} has empty field {field!r}"

    def test_persona_ids_unique(self):
        """No duplicate IDs — dict keys match persona.id attributes."""
        ids = [p.id for p in PERSONA_REGISTRY.values()]
        assert len(ids) == len(set(ids))
        for key, persona in PERSONA_REGISTRY.items():
            assert key == persona.id

    def test_procedure_backstories_coverage(self):
        """All persona IDs present in each procedure backstory."""
        for proc_type, backstories in PROCEDURE_BACKSTORIES.items():
            for pid in EXPECTED_PERSONA_IDS:
                assert pid in backstories, f"Persona {pid!r} missing from PROCEDURE_BACKSTORIES[{proc_type!r}]"

    def test_cardiac_surgery_general_fallback(self):
        """Fallback variant exists for all personas."""
        fallback = PROCEDURE_BACKSTORIES["cardiac_surgery_general"]
        for pid in EXPECTED_PERSONA_IDS:
            assert pid in fallback
            assert fallback[pid]  # non-empty string

    def test_persona_lookup_by_id(self):
        """PERSONA_REGISTRY['maria'] returns Maria."""
        maria = PERSONA_REGISTRY["maria"]
        assert isinstance(maria, Persona)
        assert maria.name == "Maria"
        assert maria.id == "maria"

    def test_persona_prompt_template_not_empty(self):
        """Each persona has a system prompt."""
        for pid, persona in PERSONA_REGISTRY.items():
            assert persona.system_prompt_template.strip(), f"Persona {pid!r} has empty system_prompt_template"

    def test_persona_weekly_prompt_not_empty(self):
        """Each persona has a weekly prompt."""
        for pid, persona in PERSONA_REGISTRY.items():
            assert persona.weekly_prompt.strip(), f"Persona {pid!r} has empty weekly_prompt"


class TestPersonaHelpers:
    def test_get_persona_helper(self):
        """get_persona() returns correct persona or None."""
        assert get_persona("maria") is PERSONA_REGISTRY["maria"]
        assert get_persona("james") is PERSONA_REGISTRY["james"]
        assert get_persona("nonexistent") is None

    def test_get_procedure_backstory_helper(self):
        """get_procedure_backstory() works correctly."""
        # Known procedure type
        backstory = get_procedure_backstory("cabg", "tony")
        assert backstory == "CABG"

        # Unknown procedure type falls back to cardiac_surgery_general
        backstory = get_procedure_backstory("unknown_procedure", "maria")
        assert backstory == PROCEDURE_BACKSTORIES["cardiac_surgery_general"]["maria"]

        # Unknown persona_id within a known procedure falls back to "heart surgery"
        backstory = get_procedure_backstory("cabg", "nobody")
        assert backstory == "heart surgery"

    def test_build_persona_prompt_helper(self):
        """build_persona_prompt() substitutes variables."""
        persona = PERSONA_REGISTRY["maria"]
        patient_context = {"procedure_type": "cabg"}

        prompt = build_persona_prompt(persona, patient_context)

        # Should contain substituted values, not raw template placeholders
        assert "{procedure}" not in prompt
        assert "{months_post_op}" not in prompt
        assert "{background}" not in prompt
        assert "{memory_context}" not in prompt

        # Should contain actual persona data
        assert persona.background in prompt
        assert str(persona.months_post_op) in prompt

    def test_build_persona_prompt_with_memory(self):
        """build_persona_prompt() includes memory context when provided."""
        persona = PERSONA_REGISTRY["james"]
        patient_context = {"procedure_type": "valve_replacement"}

        prompt = build_persona_prompt(persona, patient_context, memory="Patient prefers morning walks.")

        assert "Patient prefers morning walks." in prompt
        assert "previous conversations" in prompt
