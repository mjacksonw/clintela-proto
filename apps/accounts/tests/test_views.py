"""Tests for accounts views."""

import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse

# Import views to ensure coverage is tracked
from apps.accounts.models import AuthAttempt, User
from apps.accounts.tokens import short_code_token_generator
from apps.accounts.views import PatientAuthSession
from apps.patients.models import Hospital, Patient


@pytest.mark.django_db
class TestPatientAuthSession:
    """Test PatientAuthSession helper class."""

    def test_get_pending_auth_returns_none_when_empty(self):
        """Test get_pending_auth returns None values when session is empty."""
        client = Client()
        request = client.get("/").wsgi_request
        result = PatientAuthSession.get_pending_auth(request)
        assert result == {"token": None, "code": None, "patient_id": None}

    def test_set_and_get_pending_auth(self):
        """Test setting and getting pending auth data."""
        client = Client()
        request = client.get("/").wsgi_request

        PatientAuthSession.set_pending_auth(request, "token123", "CODE456", "patient789")
        result = PatientAuthSession.get_pending_auth(request)

        assert result == {"token": "token123", "code": "CODE456", "patient_id": "patient789"}

    def test_clear_pending_auth(self):
        """Test clearing pending auth data."""
        client = Client()
        request = client.get("/").wsgi_request

        PatientAuthSession.set_pending_auth(request, "token123", "CODE456", "patient789")
        PatientAuthSession.clear_pending_auth(request)
        result = PatientAuthSession.get_pending_auth(request)

        assert result == {"token": None, "code": None, "patient_id": None}

    def test_create_session(self):
        """Test creating authenticated session."""
        client = Client()
        request = client.get("/").wsgi_request

        PatientAuthSession.create_session(request, "patient123", PatientAuthSession.AUTH_METHOD_SMS_LINK)

        assert request.session.get(PatientAuthSession.PATIENT_ID) == "patient123"
        assert request.session.get(PatientAuthSession.AUTHENTICATED) is True
        assert request.session.get(PatientAuthSession.AUTH_METHOD) == PatientAuthSession.AUTH_METHOD_SMS_LINK
        assert PatientAuthSession.AUTHENTICATED_AT in request.session

    def test_get_patient_id_when_authenticated(self):
        """Test getting patient ID when authenticated."""
        client = Client()
        request = client.get("/").wsgi_request

        PatientAuthSession.create_session(request, "patient123")
        result = PatientAuthSession.get_patient_id(request)

        assert result == "patient123"

    def test_get_patient_id_when_not_authenticated(self):
        """Test getting patient ID when not authenticated."""
        client = Client()
        request = client.get("/").wsgi_request

        # Set patient_id but not authenticated flag
        request.session[PatientAuthSession.PATIENT_ID] = "patient123"
        request.session[PatientAuthSession.AUTHENTICATED] = False

        result = PatientAuthSession.get_patient_id(request)

        assert result is None

    def test_auth_method_constants(self):
        """Test auth method constants are defined."""
        assert PatientAuthSession.AUTH_METHOD_SMS_LINK == "sms_link"
        assert PatientAuthSession.AUTH_METHOD_MANUAL == "manual"
        assert PatientAuthSession.AUTH_METHOD_MAGIC_LINK == "magic_link"


@pytest.mark.django_db
class TestStartView:
    """Test start_view."""

    def setup_method(self):
        """Set up test patient and token."""
        self.client = Client()
        self.user = User.objects.create_user(username="startuser", password="testpass")
        self.hospital = Hospital.objects.create(name="Start Hospital", code="STA001")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1990-01-15",
            leaflet_code="A3B9K2",
        )
        self.token = short_code_token_generator.make_token(self.patient)
        self.short_code = short_code_token_generator.get_short_code(self.token)

    def test_start_view_with_valid_params(self):
        """Test start_view with valid token, code, and patient_id."""
        response = self.client.get(
            reverse("accounts:start"),
            {
                "code": self.short_code,
                "token": self.token,
                "patient_id": self.patient.id,
            },
        )

        assert response.status_code == 200
        assert "accounts/dob_entry.html" in [t.name for t in response.templates]
        assert response.context["code"] == self.short_code
        assert response.context["patient"] == self.patient

        # Verify session data is set
        assert self.client.session.get("pending_auth_token") == self.token
        assert self.client.session.get("pending_auth_code") == self.short_code
        assert self.client.session.get("pending_auth_patient_id") == str(self.patient.id)

    def test_start_view_missing_code(self):
        """Test start_view redirects to token_expired when code is missing."""
        response = self.client.get(
            reverse("accounts:start"),
            {
                "token": self.token,
                "patient_id": self.patient.id,
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

        messages_list = list(get_messages(response.wsgi_request))
        assert len(messages_list) == 1
        assert "Invalid link" in messages_list[0].message

    def test_start_view_missing_token(self):
        """Test start_view redirects to token_expired when token is missing."""
        response = self.client.get(
            reverse("accounts:start"),
            {
                "code": self.short_code,
                "patient_id": self.patient.id,
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

    def test_start_view_missing_patient_id(self):
        """Test start_view redirects to token_expired when patient_id is missing."""
        response = self.client.get(
            reverse("accounts:start"),
            {
                "code": self.short_code,
                "token": self.token,
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

    def test_start_view_invalid_patient_id_format(self):
        """Test start_view redirects to token_expired with invalid patient_id format."""
        response = self.client.get(
            reverse("accounts:start"),
            {
                "code": self.short_code,
                "token": self.token,
                "patient_id": "not-a-number",
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

    def test_start_view_nonexistent_patient(self):
        """Test start_view redirects to token_expired when patient doesn't exist."""
        response = self.client.get(
            reverse("accounts:start"),
            {
                "code": self.short_code,
                "token": self.token,
                "patient_id": 99999,
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

    def test_start_view_invalid_token(self):
        """Test start_view redirects to token_expired with invalid token."""
        response = self.client.get(
            reverse("accounts:start"),
            {
                "code": self.short_code,
                "token": "invalid-token",
                "patient_id": self.patient.id,
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

    def test_start_view_code_mismatch(self):
        """Test start_view redirects to token_expired when code doesn't match token."""
        response = self.client.get(
            reverse("accounts:start"),
            {
                "code": "WRONG00",
                "token": self.token,
                "patient_id": self.patient.id,
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

        messages_list = list(get_messages(response.wsgi_request))
        assert len(messages_list) == 1
        assert "Code mismatch" in messages_list[0].message


@pytest.mark.django_db
class TestTokenExpiredView:
    """Test token_expired_view."""

    def test_token_expired_view_renders_template(self):
        """Test token_expired_view renders the correct template."""
        client = Client()
        response = client.get(reverse("accounts:token_expired"))

        assert response.status_code == 200
        assert "accounts/token_expired.html" in [t.name for t in response.templates]


@pytest.mark.django_db
class TestVerifyDobView:
    """Test verify_dob_view."""

    def setup_method(self):
        """Set up test patient and token."""
        self.client = Client()
        self.user = User.objects.create_user(username="verifyuser", password="testpass")
        self.hospital = Hospital.objects.create(name="Verify Hospital", code="VER001")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1990-01-15",
            leaflet_code="A3B9K2",
        )
        self.token = short_code_token_generator.make_token(self.patient)
        self.short_code = short_code_token_generator.get_short_code(self.token)

        # Set up session
        session = self.client.session
        session["pending_auth_token"] = self.token
        session["pending_auth_code"] = self.short_code
        session["pending_auth_patient_id"] = str(self.patient.id)
        session.save()

    def test_verify_dob_success(self):
        """Test successful DOB verification."""
        response = self.client.post(
            reverse("accounts:verify_dob"),
            {"dob": "01/15/1990"},  # Correct DOB
        )

        assert response.status_code == 302
        assert response.url == reverse("patients:dashboard")

        # Verify session is created
        assert self.client.session.get("patient_id") == str(self.patient.id)
        assert self.client.session.get("authenticated") is True

        # Verify pending auth is cleared
        assert "pending_auth_token" not in self.client.session
        assert "pending_auth_code" not in self.client.session
        assert "pending_auth_patient_id" not in self.client.session

        # Verify AuthAttempt was logged
        attempts = AuthAttempt.objects.filter(patient=self.patient, success=True)
        assert attempts.count() == 1

    def test_verify_dob_success_iso_format(self):
        """Test successful DOB verification with ISO date format."""
        response = self.client.post(
            reverse("accounts:verify_dob"),
            {"dob": "1990-01-15"},  # ISO format
        )

        assert response.status_code == 302
        assert response.url == reverse("patients:dashboard")

    def test_verify_dob_no_session_data(self):
        """Test verify_dob_view when no pending auth in session."""
        client = Client()  # Fresh client with no session

        response = client.post(
            reverse("accounts:verify_dob"),
            {"dob": "01/15/1990"},
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

        messages_list = list(get_messages(response.wsgi_request))
        assert len(messages_list) == 1
        assert "Session expired" in messages_list[0].message

    def test_verify_dob_patient_not_found(self):
        """Test verify_dob_view when patient no longer exists."""
        # Delete patient
        self.patient.delete()

        response = self.client.post(
            reverse("accounts:verify_dob"),
            {"dob": "01/15/1990"},
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

        messages_list = list(get_messages(response.wsgi_request))
        assert len(messages_list) == 1
        assert "Patient not found" in messages_list[0].message

    def test_verify_dob_invalid_date_format(self):
        """Test verify_dob_view with invalid date format."""
        response = self.client.post(
            reverse("accounts:verify_dob"),
            {"dob": "not-a-date"},
        )

        assert response.status_code == 200
        assert "accounts/dob_entry.html" in [t.name for t in response.templates]
        assert response.context["error"] == "Please enter a valid date"

        # Verify AuthAttempt was logged
        attempts = AuthAttempt.objects.filter(patient=self.patient, success=False)
        assert attempts.count() == 1
        assert attempts.first().failure_reason == "invalid_date_format"

    def test_verify_dob_wrong_dob(self):
        """Test verify_dob_view with wrong DOB."""
        response = self.client.post(
            reverse("accounts:verify_dob"),
            {"dob": "12/25/1985"},  # Wrong DOB
        )

        assert response.status_code == 200
        assert "accounts/dob_entry.html" in [t.name for t in response.templates]
        assert "doesn't match" in response.context["error"]

        # Verify AuthAttempt was logged
        attempts = AuthAttempt.objects.filter(patient=self.patient, success=False)
        assert attempts.count() == 1
        assert attempts.first().failure_reason == "invalid_dob"

    def test_verify_dob_logs_ip_and_user_agent(self):
        """Test that verify_dob_view logs IP address and user agent."""
        self.client.defaults["REMOTE_ADDR"] = "192.168.1.100"
        self.client.defaults["HTTP_USER_AGENT"] = "TestBrowser/1.0"

        self.client.post(
            reverse("accounts:verify_dob"),
            {"dob": "01/15/1990"},
        )

        attempt = AuthAttempt.objects.get(patient=self.patient, success=True)
        assert attempt.ip_address == "192.168.1.100"
        assert attempt.user_agent == "TestBrowser/1.0"


@pytest.mark.django_db
class TestResendLinkView:
    """Test resend_link_view."""

    def test_resend_link_success(self):
        """Test resend_link_view with valid phone number."""
        client = Client()

        response = client.post(
            reverse("accounts:resend_link"),
            {"phone_number": "(555) 123-4567"},
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

        messages_list = list(get_messages(response.wsgi_request))
        assert len(messages_list) == 1
        assert "new link has been sent" in messages_list[0].message

    def test_resend_link_empty_phone(self):
        """Test resend_link_view with empty phone number."""
        client = Client()

        response = client.post(
            reverse("accounts:resend_link"),
            {"phone_number": ""},
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

        messages_list = list(get_messages(response.wsgi_request))
        assert len(messages_list) == 1
        assert "Please enter a phone number" in messages_list[0].message

    def test_resend_link_whitespace_phone(self):
        """Test resend_link_view with whitespace-only phone number."""
        client = Client()

        response = client.post(
            reverse("accounts:resend_link"),
            {"phone_number": "   "},
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

        messages_list = list(get_messages(response.wsgi_request))
        assert len(messages_list) == 1
        assert "Please enter a phone number" in messages_list[0].message


@pytest.mark.django_db
class TestManualEntryView:
    """Test manual_entry_view."""

    def test_manual_entry_not_implemented(self):
        """Test manual_entry_view returns not implemented error."""
        client = Client()

        response = client.post(
            reverse("accounts:manual_entry"),
            {
                "code": "A3B9K2",
                "dob": "01/15/1990",
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("accounts:token_expired")

        messages_list = list(get_messages(response.wsgi_request))
        assert len(messages_list) == 1
        assert "Manual entry not yet implemented" in messages_list[0].message


@pytest.mark.django_db
class TestLogoutView:
    """Test logout_view."""

    def test_logout_clears_session(self):
        """Test logout_view clears the session."""
        client = Client()

        # Set up authenticated session
        session = client.session
        session["patient_id"] = "123"
        session["authenticated"] = True
        session["some_other_key"] = "value"
        session.save()

        response = client.post(reverse("accounts:logout"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

        # Verify session is cleared
        assert client.session.get("patient_id") is None
        assert client.session.get("authenticated") is None
        assert client.session.get("some_other_key") is None

        messages_list = list(get_messages(response.wsgi_request))
        assert len(messages_list) == 1
        assert "logged out" in messages_list[0].message

    def test_logout_requires_post(self):
        """Test logout_view requires POST method."""
        client = Client()

        response = client.get(reverse("accounts:logout"))

        assert response.status_code == 405  # Method Not Allowed

    def test_logout_no_existing_session(self):
        """Test logout_view with no existing session."""
        client = Client()

        response = client.post(reverse("accounts:logout"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

        messages_list = list(get_messages(response.wsgi_request))
        assert len(messages_list) == 1
        assert "logged out" in messages_list[0].message


@pytest.mark.django_db
class TestViewIntegration:
    """Integration tests for authentication flow."""

    def setup_method(self):
        """Set up test patient and token."""
        self.client = Client()
        self.user = User.objects.create_user(username="intuser", password="testpass")
        self.hospital = Hospital.objects.create(name="Int Hospital", code="INT001")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1990-01-15",
            leaflet_code="A3B9K2",
        )
        self.token = short_code_token_generator.make_token(self.patient)
        self.short_code = short_code_token_generator.get_short_code(self.token)

    def test_full_authentication_flow(self):
        """Test complete authentication flow from start to logout."""
        # Step 1: Start with token
        response = self.client.get(
            reverse("accounts:start"),
            {
                "code": self.short_code,
                "token": self.token,
                "patient_id": self.patient.id,
            },
        )
        assert response.status_code == 200

        # Step 2: Verify DOB
        response = self.client.post(
            reverse("accounts:verify_dob"),
            {"dob": "01/15/1990"},
        )
        assert response.status_code == 302
        assert response.url == reverse("patients:dashboard")

        # Step 3: Verify session is authenticated
        assert self.client.session.get("authenticated") is True
        assert self.client.session.get("patient_id") == str(self.patient.id)

        # Step 4: Logout
        response = self.client.post(reverse("accounts:logout"))
        assert response.status_code == 302
        assert response.url == reverse("accounts:start")

        # Step 5: Verify session is cleared
        assert self.client.session.get("authenticated") is None

    def test_failed_dob_then_success(self):
        """Test failed DOB attempt followed by success."""
        # Start
        self.client.get(
            reverse("accounts:start"),
            {
                "code": self.short_code,
                "token": self.token,
                "patient_id": self.patient.id,
            },
        )

        # Failed DOB attempt
        response = self.client.post(
            reverse("accounts:verify_dob"),
            {"dob": "wrong-date"},
        )
        assert response.status_code == 200
        assert response.context["error"] is not None

        # Failed attempts logged
        assert AuthAttempt.objects.filter(patient=self.patient, success=False).count() == 1

        # Success
        response = self.client.post(
            reverse("accounts:verify_dob"),
            {"dob": "01/15/1990"},
        )
        assert response.status_code == 302
        assert response.url == reverse("patients:dashboard")

        # Both attempts logged
        assert AuthAttempt.objects.filter(patient=self.patient).count() == 2
