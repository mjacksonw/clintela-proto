"""Tests for About Me view."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.patients.models import Hospital, Patient, PatientPreferences


@pytest.mark.django_db
class TestAboutMeView:
    """Test patient_about_me_view."""

    def setup_method(self):
        self.client = Client()
        self.user = User.objects.create_user(username="aboutmeuser", password="testpass", first_name="Test")
        self.hospital = Hospital.objects.create(name="AM Hospital", code="AM01")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1990-01-15",
            leaflet_code="ABOUT123",
        )
        # Authenticate patient session
        session = self.client.session
        session["patient_id"] = str(self.patient.id)
        session["authenticated"] = True
        session.save()

    def test_get_renders_form(self):
        """GET renders the About Me form."""
        response = self.client.get(reverse("patients:about_me"))
        assert response.status_code == 200
        assert "patients/about_me.html" in [t.name for t in response.templates]

    def test_get_creates_empty_preferences(self):
        """GET creates empty preferences if none exist."""
        assert not PatientPreferences.objects.filter(patient=self.patient).exists()
        self.client.get(reverse("patients:about_me"))
        assert PatientPreferences.objects.filter(patient=self.patient).exists()

    def test_get_loads_existing_preferences(self):
        """GET loads existing preferences into context."""
        PatientPreferences.objects.create(patient=self.patient, preferred_name="TestName")
        response = self.client.get(reverse("patients:about_me"))
        assert response.context["preferences"].preferred_name == "TestName"

    def test_post_saves_preferences(self):
        """POST saves preference data."""
        response = self.client.post(
            reverse("patients:about_me"),
            {
                "preferred_name": "Bobby",
                "about_me": "Retired postal worker",
                "living_situation": "Lives with wife",
                "recovery_goals": "Tend the garden",
                "concerns": "Stairs",
                "support_network": "Wife and kids",
                "communication_style": "direct",
                "preferred_contact_time": "Afternoons",
            },
        )
        assert response.status_code == 302
        assert response.url == reverse("patients:about_me")

        prefs = PatientPreferences.objects.get(patient=self.patient)
        assert prefs.preferred_name == "Bobby"
        assert prefs.about_me == "Retired postal worker"
        assert prefs.communication_style == "direct"

    def test_post_updates_existing_preferences(self):
        """POST updates existing preferences."""
        PatientPreferences.objects.create(patient=self.patient, preferred_name="Old Name")
        self.client.post(
            reverse("patients:about_me"),
            {"preferred_name": "New Name"},
        )
        prefs = PatientPreferences.objects.get(patient=self.patient)
        assert prefs.preferred_name == "New Name"

    def test_post_strips_whitespace(self):
        """POST strips whitespace from fields."""
        self.client.post(
            reverse("patients:about_me"),
            {"preferred_name": "  Bobby  ", "about_me": "  Retired  "},
        )
        prefs = PatientPreferences.objects.get(patient=self.patient)
        assert prefs.preferred_name == "Bobby"
        assert prefs.about_me == "Retired"

    def test_requires_authentication(self):
        """View redirects unauthenticated users."""
        client = Client()  # Fresh client, no session
        response = client.get(reverse("patients:about_me"))
        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

    def test_post_success_message(self):
        """POST shows success message."""
        response = self.client.post(
            reverse("patients:about_me"),
            {"preferred_name": "Bobby"},
            follow=True,
        )
        messages = list(response.context.get("messages", []))
        assert any("Thanks for sharing" in str(m) for m in messages)
