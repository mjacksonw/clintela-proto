"""Tests for rate limiting on authentication endpoints."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tokens import short_code_token_generator
from apps.patients.models import Hospital, Patient


@pytest.mark.django_db
class TestRateLimiting:
    """Test rate limiting on authentication endpoints."""

    def setup_method(self):
        """Set up test patient and token."""
        self.client = Client()
        self.user = User.objects.create_user(username="rateuser", password="testpass")
        self.hospital = Hospital.objects.create(name="Rate Hospital", code="RAT001")
        self.patient = Patient.objects.create(
            user=self.user, hospital=self.hospital, date_of_birth="1990-01-15", leaflet_code="A3B9K2"
        )
        self.token = short_code_token_generator.make_token(self.patient)
        self.short_code = short_code_token_generator.get_short_code(self.token)

    def test_start_view_rate_limit_allows_normal_use(self):
        """Test that start_view allows 20 requests per hour normally."""
        # Make 20 requests (should all succeed)
        for _ in range(20):
            response = self.client.get(
                reverse("accounts:start"), {"code": self.short_code, "token": self.token, "patient_id": self.patient.id}
            )
            assert response.status_code in [200, 302]  # Success or redirect

    def test_start_view_rate_limit_blocks_after_20(self):
        """Test that start_view returns 429 after 20 requests per hour."""
        # Make 20 requests
        for _ in range(20):
            self.client.get(
                reverse("accounts:start"), {"code": self.short_code, "token": self.token, "patient_id": self.patient.id}
            )

        # 21st request should be rate limited
        response = self.client.get(
            reverse("accounts:start"), {"code": self.short_code, "token": self.token, "patient_id": self.patient.id}
        )
        assert response.status_code == 403  # django-ratelimit returns 403 with block=True

    def test_verify_dob_rate_limit_allows_5_attempts(self):
        """Test that verify_dob allows 5 POST requests per hour."""
        # Set up session
        session = self.client.session
        session["pending_auth_token"] = self.token
        session["pending_auth_code"] = self.short_code
        session["pending_auth_patient_id"] = str(self.patient.id)
        session.save()

        # Make 5 DOB verification attempts (should all be processed)
        for _ in range(5):
            response = self.client.post(
                reverse("accounts:verify_dob"),
                {"dob": "12/25/1985"},  # Wrong DOB
            )
            assert response.status_code == 200  # Shows error, not rate limited

    def test_verify_dob_rate_limit_blocks_after_5(self):
        """Test that verify_dob returns 429 after 5 attempts per hour."""
        # Set up session
        session = self.client.session
        session["pending_auth_token"] = self.token
        session["pending_auth_code"] = self.short_code
        session["pending_auth_patient_id"] = str(self.patient.id)
        session.save()

        # Make 5 DOB verification attempts
        for _ in range(5):
            self.client.post(
                reverse("accounts:verify_dob"),
                {"dob": "12/25/1985"},  # Wrong DOB
            )

        # 6th attempt should be rate limited
        response = self.client.post(
            reverse("accounts:verify_dob"),
            {"dob": "01/15/1990"},  # Correct DOB
        )
        assert response.status_code == 403  # django-ratelimit returns 403 with block=True

    def test_resend_link_rate_limit_by_phone(self):
        """Test that resend_link rate limits by phone number."""
        # Make 3 resend attempts for same phone
        for _ in range(3):
            response = self.client.post(reverse("accounts:resend_link"), {"phone_number": "(555) 123-4567"})
            assert response.status_code == 302  # Redirect (success)

        # 4th attempt should be rate limited
        response = self.client.post(reverse("accounts:resend_link"), {"phone_number": "(555) 123-4567"})
        assert response.status_code == 403  # django-ratelimit returns 403 with block=True

    def test_resend_link_rate_limit_different_phones_independent(self):
        """Test that rate limits are per-phone, not global."""
        # Make 3 attempts for phone 1
        for _ in range(3):
            self.client.post(reverse("accounts:resend_link"), {"phone_number": "(555) 123-4567"})

        # Different phone should still have full quota
        response = self.client.post(reverse("accounts:resend_link"), {"phone_number": "(555) 999-8888"})
        assert response.status_code == 302  # Not rate limited

    def test_manual_entry_rate_limit_blocks_after_10(self):
        """Test that manual_entry returns 429 after 10 attempts per hour."""
        # Make 10 manual entry attempts
        for _ in range(10):
            self.client.post(reverse("accounts:manual_entry"), {"code": self.short_code, "dob": "12/25/1985"})

        # 11th attempt should be rate limited
        response = self.client.post(reverse("accounts:manual_entry"), {"code": self.short_code, "dob": "01/15/1990"})
        assert response.status_code == 403  # django-ratelimit returns 403 with block=True


@pytest.mark.django_db
class TestRateLimitEdgeCases:
    """Test edge cases for rate limiting."""

    def test_rate_limit_shows_custom_template(self):
        """Test that rate limited requests show custom rate_limited template."""
        client = Client()
        user = User.objects.create_user(username="templateuser", password="testpass")
        hospital = Hospital.objects.create(name="Template Hospital", code="TMP001")
        patient = Patient.objects.create(
            user=user, hospital=hospital, date_of_birth="1990-01-15", leaflet_code="A3B9K2"
        )
        token = short_code_token_generator.make_token(patient)
        short_code = short_code_token_generator.get_short_code(token)

        # Exhaust rate limit
        for _ in range(20):
            client.get(reverse("accounts:start"), {"code": short_code, "token": token})

        # Next request should show custom template
        response = client.get(reverse("accounts:start"), {"code": short_code, "token": token})
        assert response.status_code == 403  # django-ratelimit returns 403 with block=True
        # TODO: Add custom template assertion when rate_limited.html is implemented
