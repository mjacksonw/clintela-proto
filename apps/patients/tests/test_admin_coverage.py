"""Coverage tests for patients admin configuration."""

from datetime import date

import pytest
from django.contrib.admin.sites import AdminSite

from apps.accounts.models import User
from apps.patients.admin import PatientAdmin
from apps.patients.models import Hospital, Patient


@pytest.mark.django_db
class TestPatientAdmin:
    def test_get_full_name(self):
        site = AdminSite()
        hospital = Hospital.objects.create(name="Admin Pat Hospital")
        user = User.objects.create_user(
            username="admin_cov_pat",
            password="test",  # pragma: allowlist secret
            first_name="Test",
            last_name="Admin",
        )
        patient = Patient.objects.create(user=user, hospital=hospital, date_of_birth=date(1970, 1, 1))
        admin = PatientAdmin(Patient, site)
        assert admin.get_full_name(patient) == "Test Admin"

    def test_get_days_post_op_with_surgery(self):
        site = AdminSite()
        hospital = Hospital.objects.create(name="Admin Days Hospital")
        user = User.objects.create_user(
            username="admin_days_pat",
            password="test",  # pragma: allowlist secret
            first_name="Days",
        )
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth=date(1970, 1, 1),
            surgery_date=date.today(),
        )
        admin = PatientAdmin(Patient, site)
        result = admin.get_days_post_op(patient)
        assert "days" in result

    def test_get_days_post_op_no_surgery(self):
        site = AdminSite()
        hospital = Hospital.objects.create(name="Admin No Surgery Hospital")
        user = User.objects.create_user(
            username="admin_nosurg_pat",
            password="test",  # pragma: allowlist secret
        )
        patient = Patient.objects.create(user=user, hospital=hospital, date_of_birth=date(1970, 1, 1))
        admin = PatientAdmin(Patient, site)
        assert admin.get_days_post_op(patient) == "—"

    def test_get_auth_url(self):
        site = AdminSite()
        hospital = Hospital.objects.create(name="Admin Auth Hospital")
        user = User.objects.create_user(
            username="admin_auth_pat",
            password="test",  # pragma: allowlist secret
        )
        patient = Patient.objects.create(user=user, hospital=hospital, date_of_birth=date(1970, 1, 1))
        admin = PatientAdmin(Patient, site)
        result = admin.get_auth_url(patient)
        assert "/accounts/start/" in str(result)

    def test_get_auth_url_unsaved(self):
        site = AdminSite()
        patient = Patient()  # Unsaved — no pk
        admin = PatientAdmin(Patient, site)
        result = admin.get_auth_url(patient)
        assert "Save" in result
