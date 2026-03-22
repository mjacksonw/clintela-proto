"""Tests for PatientPreferences model."""

import pytest

from apps.accounts.models import User
from apps.patients.models import Hospital, Patient, PatientPreferences


@pytest.mark.django_db
class TestPatientPreferencesModel:
    """Test PatientPreferences model."""

    def setup_method(self):
        self.user = User.objects.create_user(username="prefuser", password="testpass")
        self.hospital = Hospital.objects.create(name="Pref Hospital", code="PREF01")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1990-01-15",
            leaflet_code="PREF123",
        )

    def test_create_empty_preferences(self):
        """Preferences can be created with all blank fields."""
        prefs = PatientPreferences.objects.create(patient=self.patient)
        assert prefs.pk is not None
        assert prefs.preferred_name == ""
        assert prefs.about_me == ""
        assert not prefs.has_any_preferences

    def test_create_full_preferences(self):
        """Preferences can be created with all fields populated."""
        prefs = PatientPreferences.objects.create(
            patient=self.patient,
            preferred_name="Bobby",
            about_me="Retired postal worker",
            living_situation="Lives with wife",
            daily_routines="Morning person",
            recovery_goals="Tend the garden",
            values="Self-reliance",
            concerns="Gardening restrictions",
            communication_style="conversational",
            preferred_contact_time="Afternoons",
            support_network="Wife and kids",
        )
        assert prefs.preferred_name == "Bobby"
        assert prefs.has_any_preferences

    def test_one_to_one_relationship(self):
        """Each patient has at most one preferences record."""
        from django.db import IntegrityError

        PatientPreferences.objects.create(patient=self.patient, preferred_name="Test")
        with pytest.raises(IntegrityError):
            PatientPreferences.objects.create(patient=self.patient, preferred_name="Dup")

    def test_display_name_preferred(self):
        """display_name returns preferred_name when set."""
        prefs = PatientPreferences.objects.create(patient=self.patient, preferred_name="Bobby")
        assert prefs.display_name == "Bobby"

    def test_display_name_fallback(self):
        """display_name falls back to first name when preferred_name is blank."""
        prefs = PatientPreferences.objects.create(patient=self.patient)
        assert prefs.display_name == self.user.first_name

    def test_has_any_preferences_partial(self):
        """has_any_preferences returns True with even one field populated."""
        prefs = PatientPreferences.objects.create(patient=self.patient, recovery_goals="Get back to running")
        assert prefs.has_any_preferences

    def test_cascade_delete(self):
        """Preferences are deleted when patient is deleted."""
        PatientPreferences.objects.create(patient=self.patient, preferred_name="Test")
        assert PatientPreferences.objects.count() == 1
        self.patient.delete()
        assert PatientPreferences.objects.count() == 0

    def test_reverse_relation(self):
        """Patient.preferences works as reverse relation."""
        PatientPreferences.objects.create(patient=self.patient, preferred_name="Bobby")
        assert self.patient.preferences.preferred_name == "Bobby"

    def test_str_representation(self):
        """String representation includes patient name."""
        prefs = PatientPreferences.objects.create(patient=self.patient, preferred_name="Bobby")
        assert "Bobby" in str(prefs)

    def test_communication_style_choices(self):
        """Communication style choices are valid."""
        for choice_value, _ in PatientPreferences.COMMUNICATION_STYLE_CHOICES:
            prefs = PatientPreferences(patient=self.patient, communication_style=choice_value)
            assert prefs.communication_style == choice_value
