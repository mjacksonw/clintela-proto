"""Tests for patients views."""

from unittest.mock import patch

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


@pytest.mark.django_db
class TestPatientDashboardDebugMode:
    """Test dashboard in DEBUG mode."""

    def test_dashboard_includes_all_patients_in_debug(self, settings):
        """In DEBUG mode, dashboard includes all_patients in context."""
        settings.DEBUG = True

        user = User.objects.create_user(username="debuguser", password="testpass")
        hospital = Hospital.objects.create(name="Debug Hospital", code="DBG001")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1990-01-01",
            leaflet_code="DBG001",
        )

        client = Client()
        session = client.session
        session["patient_id"] = str(patient.id)
        session["authenticated"] = True
        session.save()

        response = client.get(reverse("patients:dashboard"))

        assert response.status_code == 200
        assert "all_patients" in response.context

    def test_dashboard_no_all_patients_when_not_debug(self, settings):
        """In non-DEBUG mode, all_patients not in context."""
        settings.DEBUG = False

        user = User.objects.create_user(username="nondebuguser", password="testpass")
        hospital = Hospital.objects.create(name="NonDebug Hospital", code="NDB001")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1990-01-01",
            leaflet_code="NDB001",
        )

        client = Client()
        session = client.session
        session["patient_id"] = str(patient.id)
        session["authenticated"] = True
        session.save()

        response = client.get(reverse("patients:dashboard"))

        assert response.status_code == 200
        assert "all_patients" not in response.context


@pytest.mark.django_db
class TestPatientDashboardConversationError:
    """Test dashboard handles conversation errors gracefully."""

    def test_dashboard_handles_conversation_exception(self):
        """Dashboard handles exception from ConversationService gracefully."""
        user = User.objects.create_user(username="convuser", password="testpass")
        hospital = Hospital.objects.create(name="Conv Hospital", code="CVH001")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1990-01-01",
            leaflet_code="CVH001",
        )

        client = Client()
        session = client.session
        session["patient_id"] = str(patient.id)
        session["authenticated"] = True
        session.save()

        with patch(
            "apps.agents.services.ConversationService.get_or_create_conversation",
            side_effect=Exception("DB error"),
        ):
            response = client.get(reverse("patients:dashboard"))

        # Should still render the dashboard, just with empty messages
        assert response.status_code == 200
        assert response.context["messages"] == []


@pytest.mark.django_db
class TestDevActionsView:
    """Test patient_dev_actions_view."""

    def setup_method(self):
        self.user = User.objects.create_user(username="devactuser", password="testpass")
        self.hospital = Hospital.objects.create(name="Dev Hospital", code="DEV001")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1990-01-01",
            leaflet_code="DEV001",
        )

    def _get_authenticated_client(self):
        client = Client()
        session = client.session
        session["patient_id"] = str(self.patient.id)
        session["authenticated"] = True
        session.save()
        return client

    def test_dev_actions_returns_404_in_production(self, settings):
        """Returns 404 when DEBUG=False."""
        settings.DEBUG = False
        client = self._get_authenticated_client()
        response = client.post(reverse("patients:dev_actions"), {"action": "clear_conversation"})
        assert response.status_code == 404

    def test_dev_actions_returns_405_for_get(self, settings):
        """Returns 405 for GET requests."""
        settings.DEBUG = True
        client = self._get_authenticated_client()
        response = client.get(reverse("patients:dev_actions"))
        assert response.status_code == 405

    def test_clear_conversation_action(self, settings):
        """clear_conversation action deletes conversations."""
        settings.DEBUG = True
        from apps.agents.models import AgentConversation
        from apps.agents.tests.factories import AgentConversationFactory

        AgentConversationFactory(patient=self.patient)
        assert AgentConversation.objects.filter(patient=self.patient).count() == 1

        client = self._get_authenticated_client()
        response = client.post(reverse("patients:dev_actions"), {"action": "clear_conversation"})

        assert response.status_code == 302
        assert AgentConversation.objects.filter(patient=self.patient).count() == 0

    def test_switch_patient_action(self, settings):
        """switch_patient action updates the session patient_id."""
        settings.DEBUG = True

        other_user = User.objects.create_user(username="otherpatient", password="testpass")
        other_patient = Patient.objects.create(
            user=other_user,
            hospital=self.hospital,
            date_of_birth="1992-01-01",
            leaflet_code="OTH001",
        )

        client = self._get_authenticated_client()
        response = client.post(
            reverse("patients:dev_actions"),
            {"action": "switch_patient", "patient_id": str(other_patient.id)},
        )

        assert response.status_code == 302
        # Session should now have the other patient's ID
        assert str(client.session.get("patient_id")) == str(other_patient.id)

    def test_switch_patient_nonexistent_id(self, settings):
        """switch_patient with nonexistent ID is handled gracefully."""
        settings.DEBUG = True
        client = self._get_authenticated_client()
        response = client.post(
            reverse("patients:dev_actions"),
            {"action": "switch_patient", "patient_id": "99999999"},
        )
        assert response.status_code == 302

    def test_simulate_sms_action(self, settings):
        """simulate_sms action triggers inbound SMS processing."""
        settings.DEBUG = True
        settings.SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
        settings.ENABLE_SMS = True
        from apps.messages_app.backends import LocMemSMSBackend, _import_sms_backend_class

        _import_sms_backend_class.cache_clear()
        LocMemSMSBackend.reset()

        client = self._get_authenticated_client()
        with patch("apps.messages_app.services.SMSService.handle_inbound_sms") as mock_handle:
            response = client.post(
                reverse("patients:dev_actions"),
                {"action": "simulate_sms", "sms_text": "Hello from SMS"},
            )
        assert response.status_code == 302
        mock_handle.assert_called_once()

    def test_simulate_sms_no_text_is_noop(self, settings):
        """simulate_sms with empty text does nothing."""
        settings.DEBUG = True

        client = self._get_authenticated_client()
        with patch("apps.messages_app.services.SMSService.handle_inbound_sms") as mock_handle:
            response = client.post(
                reverse("patients:dev_actions"),
                {"action": "simulate_sms", "sms_text": ""},
            )
        assert response.status_code == 302
        mock_handle.assert_not_called()

    def test_simulate_sms_unauthenticated_is_noop(self, settings):
        """simulate_sms without authentication does nothing."""
        settings.DEBUG = True

        client = Client()  # no session
        with patch("apps.messages_app.services.SMSService.handle_inbound_sms") as mock_handle:
            response = client.post(
                reverse("patients:dev_actions"),
                {"action": "simulate_sms", "sms_text": "Hello"},
            )
        # Still redirects (no crash)
        assert response.status_code == 302
        mock_handle.assert_not_called()

    def test_unknown_action_redirects(self, settings):
        """Unknown action still redirects to dashboard."""
        settings.DEBUG = True
        client = self._get_authenticated_client()
        response = client.post(reverse("patients:dev_actions"), {"action": "unknown_action"})
        assert response.status_code == 302


@pytest.mark.django_db
class TestSuggestionChips:
    """Test _get_suggestion_chips fallback behavior."""

    def test_default_chips_returned_when_no_pathway(self):
        """Returns default chips when no pathway exists."""
        from apps.patients.views import _get_suggestion_chips

        user = User.objects.create_user(username="chipuser", password="testpass")
        hospital = Hospital.objects.create(name="Chip Hospital", code="CHIP01")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1990-01-01",
            leaflet_code="CHIP01",
        )

        chips = _get_suggestion_chips(patient)
        assert chips == ["Is this normal?", "My medications", "Talk to my care team"]

    def test_default_chips_returned_on_exception(self):
        """Returns default chips when exception occurs."""
        from apps.patients.views import _get_suggestion_chips

        user = User.objects.create_user(username="chipexcuser", password="testpass")
        hospital = Hospital.objects.create(name="Chip Exc Hospital", code="CHEX01")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1990-01-01",
            leaflet_code="CHEX01",
        )

        with patch("apps.pathways.models.PatientPathway.objects.filter", side_effect=Exception("DB error")):
            chips = _get_suggestion_chips(patient)

        assert chips == ["Is this normal?", "My medications", "Talk to my care team"]
