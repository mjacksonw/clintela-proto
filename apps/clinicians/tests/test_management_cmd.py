"""Tests for create_test_clinician management command."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.clinicians.models import Clinician
from apps.patients.models import Patient


class CreateTestClinicianTest(TestCase):
    def test_creates_clinician_and_patients(self):
        out = StringIO()
        call_command("create_test_clinician", stdout=out)

        output = out.getvalue()
        assert "Test clinician created successfully" in output
        assert "dr_smith" in output

        # Verify clinician was created
        user = User.objects.get(username="dr_smith")
        assert user.role == "clinician"
        assert Clinician.objects.filter(user=user).exists()

        # Verify patients
        assert Patient.objects.count() >= 5

    def test_custom_username(self):
        out = StringIO()
        call_command(
            "create_test_clinician",
            username="dr_custom",
            password="custom123",  # pragma: allowlist secret
            stdout=out,
        )
        assert User.objects.filter(username="dr_custom").exists()

    def test_idempotent(self):
        """Running twice should not fail or duplicate data."""
        out = StringIO()
        call_command("create_test_clinician", stdout=out)
        call_command("create_test_clinician", stdout=out)

        # Should still have exactly 1 clinician with this username
        assert User.objects.filter(username="dr_smith").count() == 1
