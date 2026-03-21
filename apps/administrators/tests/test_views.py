"""Tests for administrator dashboard views."""

import uuid as _uuid

from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.pathways.models import ClinicalPathway
from apps.patients.models import Hospital, Patient, PatientStatusTransition

_DOB = "1960-01-15"


def _code():
    return f"H-{_uuid.uuid4().hex[:8]}"


def _lc():
    return f"LC-{_uuid.uuid4().hex[:8]}"


def _make_patient(hospital, **kwargs):
    user = User.objects.create_user(
        username=f"p_{_uuid.uuid4().hex[:6]}",
        password="pass",  # pragma: allowlist secret
        role="patient",
    )
    return Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth=_DOB,
        leaflet_code=_lc(),
        **kwargs,
    )


class AdminLoginTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin_test",
            password="testpass123",  # pragma: allowlist secret
            role="admin",
        )

    def test_login_page_renders(self):
        response = self.client.get(reverse("administrators:login"))
        assert response.status_code == 200
        assert b"Administrator Dashboard" in response.content

    def test_login_success(self):
        response = self.client.post(
            reverse("administrators:login"),
            {"username": "admin_test", "password": "testpass123"},  # pragma: allowlist secret
        )
        assert response.status_code == 302
        assert response.url == reverse("administrators:dashboard")

    def test_login_wrong_password(self):
        response = self.client.post(
            reverse("administrators:login"),
            {"username": "admin_test", "password": "wrong"},  # pragma: allowlist secret
        )
        assert response.status_code == 200
        assert b"Invalid credentials" in response.content

    def test_login_non_admin_role(self):
        User.objects.create_user(
            username="clinician",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        response = self.client.post(
            reverse("administrators:login"),
            {"username": "clinician", "password": "pass"},  # pragma: allowlist secret
        )
        assert response.status_code == 200
        assert b"Invalid credentials" in response.content

    def test_logout(self):
        self.client.login(username="admin_test", password="testpass123")
        response = self.client.get(reverse("administrators:logout"))
        assert response.status_code == 302


class AdminDashboardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            password="pass",  # pragma: allowlist secret
            role="admin",
        )
        self.hospital = Hospital.objects.create(name="Test Hospital", code=_code())
        self.client.login(username="admin", password="pass")

    def test_dashboard_requires_auth(self):
        self.client.logout()
        response = self.client.get(reverse("administrators:dashboard"))
        assert response.status_code == 302

    def test_dashboard_requires_admin_role(self):
        self.client.logout()
        User.objects.create_user(username="clinician", password="pass", role="clinician")  # pragma: allowlist secret
        self.client.login(username="clinician", password="pass")
        response = self.client.get(reverse("administrators:dashboard"))
        assert response.status_code == 403

    def test_dashboard_renders(self):
        response = self.client.get(reverse("administrators:dashboard"))
        assert response.status_code == 200
        assert b"Dashboard" in response.content

    def test_hero_readmission_fragment(self):
        response = self.client.get(reverse("administrators:hero_readmission"))
        assert response.status_code == 200

    def test_hero_readmission_with_data(self):
        p = _make_patient(self.hospital)
        PatientStatusTransition.objects.create(patient=p, from_status="post_op", to_status="discharged")

        response = self.client.get(reverse("administrators:hero_readmission"))
        assert response.status_code == 200
        assert b"0.0%" in response.content

    def test_census_fragment(self):
        _make_patient(self.hospital, status="green")
        _make_patient(self.hospital, status="red")

        response = self.client.get(reverse("administrators:census"))
        assert response.status_code == 200
        assert b"2" in response.content  # total

    def test_alerts_fragment_empty(self):
        response = self.client.get(reverse("administrators:alerts"))
        assert response.status_code == 200

    def test_discharge_to_community_fragment(self):
        response = self.client.get(reverse("administrators:discharge_to_community"))
        assert response.status_code == 200

    def test_functional_improvement_fragment(self):
        response = self.client.get(reverse("administrators:functional_improvement"))
        assert response.status_code == 200
        assert b"Requires ePRO" in response.content

    def test_followup_completion_fragment(self):
        response = self.client.get(reverse("administrators:followup_completion"))
        assert response.status_code == 200

    def test_engagement_fragment(self):
        response = self.client.get(reverse("administrators:engagement"))
        assert response.status_code == 200

    def test_message_volume_fragment(self):
        response = self.client.get(reverse("administrators:message_volume"))
        assert response.status_code == 200

    def test_checkin_completion_fragment(self):
        response = self.client.get(reverse("administrators:checkin_completion"))
        assert response.status_code == 200

    def test_escalation_response_fragment(self):
        response = self.client.get(reverse("administrators:escalation_response"))
        assert response.status_code == 200

    def test_pathway_performance_fragment(self):
        response = self.client.get(reverse("administrators:pathway_performance"))
        assert response.status_code == 200

    def test_hospital_filter(self):
        """Hospital filter param scopes results."""
        _make_patient(self.hospital)
        other = Hospital.objects.create(name="Other", code=_code())
        _make_patient(other)

        response = self.client.get(
            reverse("administrators:census"),
            {"hospital": self.hospital.id},
        )
        assert response.status_code == 200
        assert b"1" in response.content

    def test_days_filter(self):
        """Days filter param is accepted."""
        response = self.client.get(
            reverse("administrators:hero_readmission"),
            {"days": "90"},
        )
        assert response.status_code == 200


class CSVExportTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            password="pass",  # pragma: allowlist secret
            role="admin",
        )
        self.hospital = Hospital.objects.create(name="Test", code=_code())
        self.client.login(username="admin", password="pass")

    def test_export_csv(self):
        _make_patient(self.hospital)
        response = self.client.get(reverse("administrators:export_csv"))
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert "attachment" in response["Content-Disposition"]

    def test_export_requires_auth(self):
        self.client.logout()
        response = self.client.get(reverse("administrators:export_csv"))
        assert response.status_code == 302

    def test_csv_formula_injection_protection(self):
        """Values starting with =,-,+,@ are prefixed with tab."""
        from apps.administrators.views import _sanitize_csv_value

        assert _sanitize_csv_value("=SUM(A1)") == "\t=SUM(A1)"
        assert _sanitize_csv_value("-cmd") == "\t-cmd"
        assert _sanitize_csv_value("+1") == "\t+1"
        assert _sanitize_csv_value("@import") == "\t@import"
        assert _sanitize_csv_value("Normal") == "Normal"
        assert _sanitize_csv_value("123") == "123"


class PathwayAdminTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            password="pass",  # pragma: allowlist secret
            role="admin",
        )
        self.hospital = Hospital.objects.create(name="Test", code=_code())
        self.pathway = ClinicalPathway.objects.create(
            name="Test Pathway",
            surgery_type="cardiac",
            duration_days=30,
        )
        self.client.login(username="admin", password="pass")

    def test_pathway_list(self):
        response = self.client.get(reverse("administrators:pathway_list"))
        assert response.status_code == 200
        assert b"Test Pathway" in response.content

    def test_pathway_detail(self):
        response = self.client.get(reverse("administrators:pathway_detail", args=[self.pathway.id]))
        assert response.status_code == 200
        assert b"Test Pathway" in response.content

    def test_pathway_detail_not_found(self):
        response = self.client.get(reverse("administrators:pathway_detail", args=[9999]))
        assert response.status_code == 404

    def test_pathway_toggle(self):
        assert self.pathway.is_active is True
        response = self.client.post(reverse("administrators:pathway_toggle", args=[self.pathway.id]))
        assert response.status_code == 200
        self.pathway.refresh_from_db()
        assert self.pathway.is_active is False

    def test_pathway_edit(self):
        response = self.client.post(
            reverse("administrators:pathway_edit", args=[self.pathway.id]),
            {"name": "Updated Name", "description": "New desc", "duration_days": "60"},
        )
        assert response.status_code == 200
        self.pathway.refresh_from_db()
        assert self.pathway.name == "Updated Name"
        assert self.pathway.duration_days == 60

    def test_pathway_edit_empty_name(self):
        response = self.client.post(
            reverse("administrators:pathway_edit", args=[self.pathway.id]),
            {"name": "", "description": "desc", "duration_days": "30"},
        )
        assert response.status_code == 200
        assert b"Name is required" in response.content

    def test_pathway_requires_auth(self):
        self.client.logout()
        response = self.client.get(reverse("administrators:pathway_list"))
        assert response.status_code == 302


class ManagementCommandTest(TestCase):
    def test_create_test_admin(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("create_test_admin", stdout=out)
        assert User.objects.filter(username="admin_test", role="admin").exists()
        assert "Created admin user" in out.getvalue()

    def test_create_test_admin_idempotent(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("create_test_admin", stdout=StringIO())
        out = StringIO()
        call_command("create_test_admin", stdout=out)
        assert "already exists" in out.getvalue()
        assert User.objects.filter(username="admin_test").count() == 1
