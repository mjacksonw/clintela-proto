"""Tests for preference-aware check-in preambles."""

import pytest

from apps.accounts.models import User
from apps.agents.tasks import _build_checkin_preamble
from apps.patients.models import Hospital, Patient, PatientPreferences


@pytest.mark.django_db
class TestCheckinPreamble:
    """Test _build_checkin_preamble function."""

    def setup_method(self):
        self.user = User.objects.create_user(username="preambleuser", password="testpass", first_name="Maria")
        self.hospital = Hospital.objects.create(name="Pre Hospital", code="PRE01")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1954-03-12",
            leaflet_code="PRE123",
        )

    def test_early_recovery_alone(self):
        """Early days + lives alone produces empathetic preamble."""
        prefs = PatientPreferences.objects.create(
            patient=self.patient,
            preferred_name="Maria",
            living_situation="Lives alone in second-floor apartment",
        )
        result = _build_checkin_preamble(prefs, day=2)
        assert "Maria" in result
        assert "alone" in result.lower()

    def test_early_recovery_default(self):
        """Early days without living situation uses default."""
        prefs = PatientPreferences.objects.create(patient=self.patient, preferred_name="Maria")
        result = _build_checkin_preamble(prefs, day=1)
        assert "Maria" in result
        assert "first few days" in result.lower()

    def test_active_recovery_with_goals(self):
        """Active recovery with goals references the goal."""
        prefs = PatientPreferences.objects.create(
            patient=self.patient,
            preferred_name="Maria",
            recovery_goals="Back to my book club by April, weekly walks",
        )
        result = _build_checkin_preamble(prefs, day=7)
        assert "Maria" in result
        assert "book club" in result.lower()

    def test_active_recovery_without_goals(self):
        """Active recovery without goals uses generic encouragement."""
        prefs = PatientPreferences.objects.create(patient=self.patient, preferred_name="Maria")
        result = _build_checkin_preamble(prefs, day=10)
        assert "Maria" in result
        assert "stronger" in result.lower()

    def test_established_recovery_with_goals(self):
        """Established recovery with goals references the goal."""
        prefs = PatientPreferences.objects.create(
            patient=self.patient,
            preferred_name="Bobby",
            recovery_goals="Tend my vegetable garden this spring",
        )
        result = _build_checkin_preamble(prefs, day=20)
        assert "Bobby" in result
        assert "garden" in result.lower()

    def test_established_recovery_without_goals(self):
        """Established recovery without goals uses day count."""
        prefs = PatientPreferences.objects.create(patient=self.patient, preferred_name="Bobby")
        result = _build_checkin_preamble(prefs, day=30)
        assert "Bobby" in result
        assert "30" in result

    def test_fallback_to_there_when_no_preferred_name(self):
        """Falls back to 'there' when no preferred name."""
        prefs = PatientPreferences.objects.create(patient=self.patient)
        result = _build_checkin_preamble(prefs, day=5)
        assert "there" in result
