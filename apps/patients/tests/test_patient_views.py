"""Tests for patients views."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.patients.models import Hospital, Patient


@pytest.mark.django_db
class TestPatientDashboardView:
    """Test patient_dashboard_view."""

    def setup_method(self):
        """Set up test patient."""
        self.client = Client()
        self.user = User.objects.create_user(username="dashuser", password="testpass")
        self.hospital = Hospital.objects.create(name="Dash Hospital", code="DASH01")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1990-01-15",
            leaflet_code="A3B9K2",
        )

    def test_dashboard_view_authenticated(self):
        """Test dashboard view when patient is authenticated."""
        # Set up authenticated session
        session = self.client.session
        session["patient_id"] = str(self.patient.id)
        session["authenticated"] = True
        session.save()

        response = self.client.get(reverse("patients:dashboard"))

        assert response.status_code == 200
        assert "patients/dashboard.html" in [t.name for t in response.templates]
        assert response.context["patient"] == self.patient

    def test_dashboard_view_not_authenticated(self):
        """Test dashboard view redirects when not authenticated."""
        response = self.client.get(reverse("patients:dashboard"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

    def test_dashboard_view_missing_patient_id(self):
        """Test dashboard view redirects when patient_id is missing."""
        session = self.client.session
        session["authenticated"] = True
        session.save()

        response = self.client.get(reverse("patients:dashboard"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

    def test_dashboard_view_missing_authenticated_flag(self):
        """Test dashboard view redirects when authenticated flag is missing."""
        session = self.client.session
        session["patient_id"] = str(self.patient.id)
        session.save()

        response = self.client.get(reverse("patients:dashboard"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

    def test_dashboard_view_authenticated_false(self):
        """Test dashboard view redirects when authenticated is False."""
        session = self.client.session
        session["patient_id"] = str(self.patient.id)
        session["authenticated"] = False
        session.save()

        response = self.client.get(reverse("patients:dashboard"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

    def test_dashboard_view_patient_not_found(self):
        """Test dashboard view redirects when patient doesn't exist."""
        # Delete patient
        self.patient.delete()

        session = self.client.session
        session["patient_id"] = "99999"
        session["authenticated"] = True
        session.save()

        response = self.client.get(reverse("patients:dashboard"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

    def test_dashboard_view_patient_id_zero(self):
        """Test dashboard view redirects with patient_id of 0."""
        session = self.client.session
        session["patient_id"] = "0"
        session["authenticated"] = True
        session.save()

        response = self.client.get(reverse("patients:dashboard"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

    def test_dashboard_view_post_method(self):
        """Test dashboard view handles POST requests (no @require_http_methods decorator)."""
        # Set up authenticated session
        session = self.client.session
        session["patient_id"] = str(self.patient.id)
        session["authenticated"] = True
        session.save()

        # POST should work since there's no @require_http_methods decorator
        response = self.client.post(reverse("patients:dashboard"))
        # The view doesn't handle POST specially, so it will render the template
        assert response.status_code == 200


@pytest.mark.django_db
class TestPatientDashboardEdgeCases:
    """Test edge cases for patient dashboard."""

    def test_dashboard_view_empty_session(self):
        """Test dashboard view with completely empty session."""
        client = Client()

        response = client.get(reverse("patients:dashboard"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

    def test_dashboard_view_session_with_other_keys(self):
        """Test dashboard view with session containing unrelated keys."""
        client = Client()
        session = client.session
        session["some_other_key"] = "some_value"
        session.save()

        response = client.get(reverse("patients:dashboard"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

    def test_dashboard_view_deleted_patient_mid_session(self):
        """Test dashboard view when patient is deleted after session created."""
        user = User.objects.create_user(username="deleteduser", password="testpass")
        hospital = Hospital.objects.create(name="Deleted Hospital", code="DEL001")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1985-05-20",
            leaflet_code="DEL999",
        )

        client = Client()
        session = client.session
        session["patient_id"] = str(patient.id)
        session["authenticated"] = True
        session.save()

        # Delete patient
        patient.delete()

        response = client.get(reverse("patients:dashboard"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")


@pytest.mark.django_db
class TestPatientDashboardContext:
    """Test context data passed to dashboard template."""

    def test_dashboard_context_contains_patient(self):
        """Test that dashboard context contains patient object."""
        user = User.objects.create_user(username="ctxuser", password="testpass")
        hospital = Hospital.objects.create(name="Context Hospital", code="CTX001")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1992-03-10",
            leaflet_code="CTX123",
        )

        client = Client()
        session = client.session
        session["patient_id"] = str(patient.id)
        session["authenticated"] = True
        session.save()

        response = client.get(reverse("patients:dashboard"))

        assert response.status_code == 200
        assert "patient" in response.context
        assert response.context["patient"].id == patient.id
        assert response.context["patient"].leaflet_code == "CTX123"

    def test_dashboard_context_patient_attributes(self):
        """Test that patient in context has expected attributes."""
        user = User.objects.create_user(username="attruser", password="testpass")
        hospital = Hospital.objects.create(name="Attr Hospital", code="ATTR01")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1988-12-25",
            leaflet_code="ATTR99",
        )

        client = Client()
        session = client.session
        session["patient_id"] = str(patient.id)
        session["authenticated"] = True
        session.save()

        response = client.get(reverse("patients:dashboard"))

        assert response.status_code == 200
        context_patient = response.context["patient"]
        assert context_patient.user == user
        assert context_patient.hospital == hospital
        assert str(context_patient.date_of_birth) == "1988-12-25"


@pytest.mark.django_db
class TestPatientDashboardIntegration:
    """Integration tests for patient dashboard with authentication flow."""

    def test_dashboard_after_full_auth_flow(self):
        """Test accessing dashboard after complete authentication.

        This test simulates the auth flow by directly setting session data,
        rather than using the full authentication flow to avoid rate limiting.
        """
        user = User.objects.create_user(username="intdashuser", password="testpass")
        hospital = Hospital.objects.create(name="Int Dash Hospital", code="INTD01")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1990-06-15",
            leaflet_code="INTD99",
        )

        client = Client()

        # Simulate successful authentication by setting session data directly
        # (In production, this would come from verify_dob_view)
        session = client.session
        session["patient_id"] = str(patient.id)
        session["authenticated"] = True
        session.save()

        # Access dashboard
        response = client.get(reverse("patients:dashboard"))

        assert response.status_code == 200
        assert response.context["patient"] == patient

    def test_dashboard_redirects_after_logout(self):
        """Test dashboard redirects after logout."""
        user = User.objects.create_user(username="logoutuser", password="testpass")
        hospital = Hospital.objects.create(name="Logout Hospital", code="OUT001")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1991-07-20",
            leaflet_code="OUT123",
        )

        client = Client()

        # Authenticate
        session = client.session
        session["patient_id"] = str(patient.id)
        session["authenticated"] = True
        session.save()

        # Verify dashboard works
        response = client.get(reverse("patients:dashboard"))
        assert response.status_code == 200

        # Logout
        client.post(reverse("accounts:logout"))

        # Verify dashboard redirects
        response = client.get(reverse("patients:dashboard"))
        assert response.status_code == 302
        assert response.url == reverse("accounts:start")
