"""Tests for demo authentication views and context processor."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.patients.models import Hospital, Patient

# Use hardcoded path instead of DEMO_LOGIN_URL because the URL is
# conditionally registered (inside `if settings.DEBUG` in urls.py). When
# xdist workers run tests that set DEBUG=False, the URL resolver cache gets
# corrupted and reverse() fails for other tests on the same worker.
DEMO_LOGIN_URL = "/demo-login/"


@pytest.mark.django_db
class TestDemoLoginView:
    """Test demo_login_view for one-click role switching."""

    def setup_method(self):
        self.client = Client()
        self.hospital = Hospital.objects.create(name="Demo Hospital", code="DEMO01")

        # Create a patient
        self.patient_user = User.objects.create_user(username="demo_patient", password="testpass", role="patient")
        self.patient = Patient.objects.create(
            user=self.patient_user,
            hospital=self.hospital,
            date_of_birth="1990-01-15",
            leaflet_code="DEMO01",
        )

        # Create a clinician
        from apps.clinicians.models import Clinician

        self.clinician_user = User.objects.create_user(username="demo_clinician", password="testpass", role="clinician")
        self.clinician = Clinician.objects.create(
            user=self.clinician_user,
            role="physician",
        )

        # Create an admin
        self.admin_user = User.objects.create_user(username="demo_admin", password="testpass", role="admin")

    # --- DEBUG guard ---

    def test_returns_404_when_not_debug(self):
        """View-level guard returns 404 when DEBUG=False."""
        from unittest.mock import patch

        from django.http import Http404
        from django.test import RequestFactory

        from apps.accounts.views_dev import demo_login_view

        factory = RequestFactory()
        request = factory.post("/demo-login/", {"role": "patient"})

        with patch("apps.accounts.views_dev.settings") as mock_settings:
            mock_settings.DEBUG = False
            with pytest.raises(Http404):
                demo_login_view(request)

    def test_returns_405_for_get(self, settings):
        settings.DEBUG = True
        response = self.client.get(DEMO_LOGIN_URL)
        assert response.status_code == 405

    # --- Happy path ---

    def test_login_as_patient(self, settings):
        settings.DEBUG = True
        response = self.client.post(DEMO_LOGIN_URL, {"role": "patient"})
        assert response.status_code == 302
        assert response.url == reverse("patients:dashboard")
        assert self.client.session.get("authenticated") is True
        assert self.client.session.get("patient_id") == str(self.patient.id)

    def test_login_as_clinician(self, settings):
        settings.DEBUG = True
        response = self.client.post(DEMO_LOGIN_URL, {"role": "clinician"})
        assert response.status_code == 302
        assert response.url == reverse("clinicians:dashboard")
        # Django auth should be set
        assert int(self.client.session["_auth_user_id"]) == self.clinician_user.id

    def test_login_as_admin(self, settings):
        settings.DEBUG = True
        response = self.client.post(DEMO_LOGIN_URL, {"role": "admin"})
        assert response.status_code == 302
        assert response.url == reverse("administrators:dashboard")
        assert int(self.client.session["_auth_user_id"]) == self.admin_user.id

    # --- Specific user selection ---

    def test_login_as_specific_patient(self, settings):
        settings.DEBUG = True
        # Create a second patient
        user2 = User.objects.create_user(username="patient2", password="testpass", role="patient")
        patient2 = Patient.objects.create(
            user=user2,
            hospital=self.hospital,
            date_of_birth="1991-02-20",
            leaflet_code="DEMO02",
        )

        response = self.client.post(
            DEMO_LOGIN_URL,
            {"role": "patient", "user_id": str(patient2.id)},
        )
        assert response.status_code == 302
        assert self.client.session.get("patient_id") == str(patient2.id)

    def test_login_as_specific_clinician(self, settings):
        settings.DEBUG = True
        response = self.client.post(
            DEMO_LOGIN_URL,
            {"role": "clinician", "user_id": str(self.clinician_user.id)},
        )
        assert response.status_code == 302
        assert int(self.client.session["_auth_user_id"]) == self.clinician_user.id

    # --- Error cases ---

    def test_invalid_role_redirects_home(self, settings):
        settings.DEBUG = True
        response = self.client.post(DEMO_LOGIN_URL, {"role": "bogus"})
        assert response.status_code == 302
        assert response.url == "/"

    def test_nonexistent_user_redirects_home(self, settings):
        settings.DEBUG = True
        response = self.client.post(
            DEMO_LOGIN_URL,
            {"role": "patient", "user_id": "99999"},
        )
        assert response.status_code == 302
        assert response.url == "/"

    # --- Role switching ---

    def test_switch_patient_to_clinician(self, settings):
        settings.DEBUG = True
        # First authenticate as patient
        session = self.client.session
        session["patient_id"] = str(self.patient.id)
        session["authenticated"] = True
        session.save()

        # Switch to clinician
        response = self.client.post(DEMO_LOGIN_URL, {"role": "clinician"})
        assert response.status_code == 302
        assert response.url == reverse("clinicians:dashboard")
        # Patient session keys should be cleared (logout flushes session)
        assert self.client.session.get("patient_id") is None
        assert int(self.client.session["_auth_user_id"]) == self.clinician_user.id

    def test_switch_clinician_to_patient(self, settings):
        settings.DEBUG = True
        # First authenticate as clinician via Django login
        self.client.force_login(self.clinician_user)

        # Switch to patient
        response = self.client.post(DEMO_LOGIN_URL, {"role": "patient"})
        assert response.status_code == 302
        assert response.url == reverse("patients:dashboard")
        assert self.client.session.get("authenticated") is True
        # Django auth should be cleared
        assert "_auth_user_id" not in self.client.session


@pytest.mark.django_db
class TestDemoBarContext:
    """Test demo_bar_context context processor."""

    def test_returns_empty_when_not_debug(self):
        """Context processor returns empty dict when DEBUG=False."""
        from unittest.mock import patch

        from django.test import RequestFactory

        from apps.accounts.context_processors import demo_bar_context

        request = RequestFactory().get("/")
        request.session = {}

        with patch("apps.accounts.context_processors.settings") as mock_settings:
            mock_settings.DEBUG = False
            result = demo_bar_context(request)
            assert result == {}

    def test_returns_all_roles_when_debug(self, settings):
        settings.DEBUG = True
        from django.test import RequestFactory

        from apps.accounts.context_processors import demo_bar_context

        hospital = Hospital.objects.create(name="Ctx Hospital", code="CTX01")
        patient_user = User.objects.create_user(username="ctx_patient", password="testpass", role="patient")
        Patient.objects.create(
            user=patient_user,
            hospital=hospital,
            date_of_birth="1990-01-01",
            leaflet_code="CTX01",
        )

        from apps.clinicians.models import Clinician

        clin_user = User.objects.create_user(username="ctx_clinician", password="testpass", role="clinician")
        Clinician.objects.create(user=clin_user, role="physician")

        User.objects.create_user(username="ctx_admin", password="testpass", role="admin")  # pragma: allowlist secret

        request = RequestFactory().get("/")
        request.session = {}
        result = demo_bar_context(request)

        assert "demo_patients" in result
        assert "demo_clinicians" in result
        assert "demo_admins" in result
        assert result["demo_patients"].count() >= 1
        assert result["demo_clinicians"].count() >= 1
        assert result["demo_admins"].count() >= 1
