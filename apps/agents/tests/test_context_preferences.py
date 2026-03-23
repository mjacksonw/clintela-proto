"""Tests for patient preferences injection into agent context."""

from datetime import date

import pytest

from apps.accounts.models import User
from apps.agents.services import ContextService
from apps.patients.models import Hospital, Patient, PatientPreferences


@pytest.mark.django_db
class TestContextPreferencesInjection:
    """Test that patient preferences are injected into agent context."""

    def setup_method(self):
        self.user = User.objects.create_user(username="ctxuser", password="testpass", first_name="Maria")
        self.hospital = Hospital.objects.create(name="Ctx Hospital", code="CTX01")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth=date(1954, 3, 12),
            leaflet_code="CTX123",
        )

    def test_context_without_preferences(self):
        """Context works normally when no preferences exist."""
        context = ContextService.get_patient_context(self.patient)
        assert "preferences" not in context
        assert context["name"] == "Maria "

    def test_context_with_empty_preferences(self):
        """Context omits preferences when all fields are blank."""
        PatientPreferences.objects.create(patient=self.patient)
        context = ContextService.get_patient_context(self.patient)
        assert "preferences" not in context

    def test_context_with_populated_preferences(self):
        """Context includes preferences when fields are populated."""
        PatientPreferences.objects.create(
            patient=self.patient,
            preferred_name="Maria",
            recovery_goals="Back to book club",
            concerns="Managing stairs",
            communication_style="detailed",
        )
        context = ContextService.get_patient_context(self.patient)
        assert "preferences" in context
        assert context["preferences"]["preferred_name"] == "Maria"
        assert context["preferences"]["recovery_goals"] == "Back to book club"
        assert context["preferences"]["concerns"] == "Managing stairs"
        assert "Detailed" in context["preferences"]["communication_style"]

    def test_preferred_name_fallback(self):
        """Preferred name falls back to first name when blank."""
        PatientPreferences.objects.create(
            patient=self.patient,
            recovery_goals="Something",  # At least one field to trigger inclusion
        )
        context = ContextService.get_patient_context(self.patient)
        assert context["preferences"]["preferred_name"] == "Maria"

    def test_full_context_includes_preferences(self):
        """assemble_full_context includes preferences via get_patient_context."""
        PatientPreferences.objects.create(
            patient=self.patient,
            preferred_name="Maria",
            about_me="Retired teacher",
        )
        full_context = ContextService.assemble_full_context(self.patient)
        assert "preferences" in full_context["patient"]
