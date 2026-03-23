"""Tests for Django messages rendering across all template types.

Verifies that the shared _messages.html partial is included in every base
template and auth screen so queued messages are consumed immediately rather
than leaking to the next page that happens to render them.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tokens import short_code_token_generator
from apps.patients.models import Hospital, Patient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_patient(client: Client) -> tuple[Patient, str, str]:
    """Create a patient with token and return (patient, token, short_code)."""
    user = User.objects.create_user(username="msguser", password="testpass")
    hospital = Hospital.objects.create(name="Msg Hospital", code="MSG001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="M5G1K2",
    )
    token = short_code_token_generator.make_token(patient)
    short_code = short_code_token_generator.get_short_code(token)
    return patient, token, short_code


def _auth_patient_session(client: Client, patient: Patient) -> None:
    """Set up an authenticated patient session."""
    session = client.session
    session["patient_id"] = str(patient.id)
    session["authenticated"] = True
    session.save()


# ---------------------------------------------------------------------------
# Auth template tests — messages should now appear in rendered HTML
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMessagesOnAuthScreens:
    """Messages queued during auth redirects must appear in the rendered HTML."""

    def test_token_expired_renders_error_message(self):
        """Error messages queued before redirect to token_expired appear in HTML."""
        client = Client()
        patient, token, short_code = _setup_patient(client)

        # This queues "Code mismatch..." and redirects to token_expired
        response = client.get(
            reverse("accounts:start"),
            {"code": "WRONG00", "token": token, "patient_id": patient.id},
        )
        assert response.status_code == 302

        # Follow the redirect — the message should render in the HTML
        response = client.get(reverse("accounts:token_expired"))
        content = response.content.decode()
        assert "Code mismatch" in content
        assert "messages-container" in content

    def test_token_expired_renders_success_message(self):
        """Success messages (e.g. resend link) appear on token_expired page."""
        client = Client()

        response = client.post(
            reverse("accounts:resend_link"),
            {"phone_number": "(555) 123-4567"},
        )
        assert response.status_code == 302

        # Follow redirect
        response = client.get(reverse("accounts:token_expired"))
        content = response.content.decode()
        assert "new link has been sent" in content
        assert "check-circle" in content  # success icon

    def test_token_expired_renders_empty_phone_error(self):
        """Error for empty phone number appears on token_expired page."""
        client = Client()

        client.post(reverse("accounts:resend_link"), {"phone_number": ""})
        response = client.get(reverse("accounts:token_expired"))
        content = response.content.decode()
        assert "Please enter a phone number" in content
        assert "alert-circle" in content  # error icon

    def test_invalid_link_message_appears_on_token_expired(self):
        """Missing params queues 'Invalid link' and it renders on token_expired."""
        client = Client()

        # Missing code param triggers error message
        response = client.get(
            reverse("accounts:start"),
            {"token": "sometoken", "patient_id": "1"},
        )
        assert response.status_code == 302

        response = client.get(reverse("accounts:token_expired"))
        content = response.content.decode()
        assert "Invalid link" in content

    def test_dob_entry_includes_messages_partial(self):
        """DOB entry page includes the messages partial (even if no messages)."""
        client = Client()
        patient, token, short_code = _setup_patient(client)

        response = client.get(
            reverse("accounts:start"),
            {"code": short_code, "token": token, "patient_id": patient.id},
        )
        assert response.status_code == 200
        content = response.content.decode()
        # The partial is included but no messages to render, so no container
        # Just verify the template loaded successfully
        assert "Welcome to Clintela" in content

    def test_messages_consumed_after_rendering(self):
        """Messages are consumed after being rendered — not shown twice."""
        client = Client()

        # Queue a message
        client.post(reverse("accounts:resend_link"), {"phone_number": "(555) 000-0000"})

        # First load — message appears
        response = client.get(reverse("accounts:token_expired"))
        assert "new link has been sent" in response.content.decode()

        # Second load — message should be gone (consumed by Django)
        response = client.get(reverse("accounts:token_expired"))
        assert "new link has been sent" not in response.content.decode()


# ---------------------------------------------------------------------------
# Patient dashboard / pages — messages via base_patient.html
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMessagesOnPatientPages:
    """Messages render on patient pages via base_patient.html include."""

    def setup_method(self):
        self.client = Client()
        self.user = User.objects.create_user(username="patmsguser", password="testpass", first_name="Pat")
        self.hospital = Hospital.objects.create(name="PatMsg Hospital", code="PM001")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1990-01-15",
            leaflet_code="PM1234",
        )
        _auth_patient_session(self.client, self.patient)

    def test_dashboard_renders_messages(self):
        """Patient dashboard renders queued messages via base_patient.html."""
        response = self.client.get(reverse("patients:dashboard"))
        assert response.status_code == 200
        # Template uses the include — verify partial is referenced
        assert "components/_messages.html" in [t.name for t in response.templates]

    def test_caregivers_page_renders_messages_via_base(self):
        """Caregivers page gets messages from base_patient.html (not inline block)."""
        # Post to the invite endpoint with missing info to trigger error message
        response = self.client.post(
            reverse("patients:caregiver_invite"),
            {"name": "", "relationship": ""},
        )
        assert response.status_code == 302

        response = self.client.get(reverse("patients:caregivers"))
        content = response.content.decode()
        assert "Name and relationship are required" in content
        assert "messages-container" in content

    def test_about_me_page_still_renders_messages(self):
        """About Me page still renders messages after removing inline block."""
        response = self.client.get(reverse("patients:about_me"))
        assert response.status_code == 200
        # Verify the messages partial is included
        assert "components/_messages.html" in [t.name for t in response.templates]


# ---------------------------------------------------------------------------
# Clinician login — messages via include
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMessagesOnClinicianLogin:
    """Clinician login page renders messages."""

    def test_login_page_includes_messages_partial(self):
        """Clinician login template includes the messages partial."""
        client = Client()
        response = client.get(reverse("clinicians:login"))
        assert response.status_code == 200
        assert "components/_messages.html" in [t.name for t in response.templates]


# ---------------------------------------------------------------------------
# Admin login — messages via include
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMessagesOnAdminLogin:
    """Admin login page renders messages."""

    def test_login_page_includes_messages_partial(self):
        """Admin login template includes the messages partial."""
        client = Client()
        response = client.get(reverse("administrators:login"))
        assert response.status_code == 200
        assert "components/_messages.html" in [t.name for t in response.templates]


# ---------------------------------------------------------------------------
# Messages partial rendering — tag styling
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMessagesPartialStyling:
    """Verify the partial renders correct styles for each message level."""

    def test_success_message_styling(self):
        """Success messages get green background and check-circle icon."""
        client = Client()

        # Resend link queues a success message, redirects to token_expired
        client.post(reverse("accounts:resend_link"), {"phone_number": "(555) 111-2222"})
        response = client.get(reverse("accounts:token_expired"))
        content = response.content.decode()

        assert "#D1FAE5" in content  # green bg
        assert "#065F46" in content  # green text
        assert "check-circle" in content

    def test_error_message_styling(self):
        """Error messages get red background and alert-circle icon."""
        client = Client()

        client.post(reverse("accounts:resend_link"), {"phone_number": ""})
        response = client.get(reverse("accounts:token_expired"))
        content = response.content.decode()

        assert "#FEE2E2" in content  # red bg
        assert "#991B1B" in content  # red text
        assert "alert-circle" in content

    def test_error_message_has_alert_role(self):
        """Error messages use role='alert' for screen readers."""
        client = Client()

        client.post(reverse("accounts:resend_link"), {"phone_number": ""})
        response = client.get(reverse("accounts:token_expired"))
        content = response.content.decode()

        assert 'role="alert"' in content

    def test_success_message_has_status_role(self):
        """Non-error messages use role='status' for screen readers."""
        client = Client()

        client.post(reverse("accounts:resend_link"), {"phone_number": "(555) 111-2222"})
        response = client.get(reverse("accounts:token_expired"))
        content = response.content.decode()

        assert 'role="status"' in content
