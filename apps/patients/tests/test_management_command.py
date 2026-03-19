"""Tests for create_test_patient management command."""

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.patients.models import Hospital, Patient


@pytest.mark.django_db
class TestCreateTestPatient:
    """Test create_test_patient management command."""

    def test_creates_hospital_user_patient(self):
        """Running the command creates Hospital, User, and Patient."""
        call_command("create_test_patient")

        assert Hospital.objects.filter(code="TEST").exists()
        assert User.objects.filter(first_name="Sarah", last_name="Chen").exists()
        assert Patient.objects.filter(user__first_name="Sarah", surgery_type="Knee Replacement").exists()

    def test_idempotent(self):
        """Running the command twice does not raise IntegrityError."""
        call_command("create_test_patient")
        call_command("create_test_patient")

        assert Hospital.objects.filter(code="TEST").count() == 1
        assert User.objects.filter(first_name="Sarah", last_name="Chen").count() == 1

    def test_outputs_auth_url(self, capsys):
        """Command output includes an auth URL."""
        call_command("create_test_patient")
        output = capsys.readouterr().out

        assert "/accounts/start/" in output
        assert "code=" in output
