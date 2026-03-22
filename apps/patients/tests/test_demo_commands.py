"""Tests for demo preparation management commands and template changes."""

import uuid as _uuid

from django.core.management import call_command
from django.template import Context, Template
from django.test import TestCase

from apps.accounts.models import User
from apps.agents.models import Escalation
from apps.analytics.models import DailyMetrics
from apps.clinicians.models import Clinician
from apps.patients.models import Hospital, Patient
from apps.patients.templatetags.patient_tags import agent_display_name
from apps.surveys.models import SurveyInstance


def _code():
    return f"TST-{_uuid.uuid4().hex[:8]}"


def _lc():
    return f"LC-{_uuid.uuid4().hex[:8]}"


class AgentDisplayNameFilterTest(TestCase):
    """Test the agent_display_name template filter."""

    def test_known_agent_types(self):
        assert agent_display_name("care_coordinator") == "Care Coordinator"
        assert agent_display_name("nurse_triage") == "Nurse"
        assert agent_display_name("specialist_cardiology") == "Cardiology Specialist"
        assert agent_display_name("specialist_pharmacy") == "Pharmacist"
        assert agent_display_name("clinician") == "Your Care Team"

    def test_unknown_agent_type_falls_back(self):
        assert agent_display_name("unknown_type") == "Assistant"

    def test_empty_string(self):
        assert agent_display_name("") == "Assistant"

    def test_used_in_template(self):
        """Verify the filter works when loaded in a template."""
        template = Template("{% load patient_tags %}{{ agent_type|agent_display_name }}")
        result = template.render(Context({"agent_type": "nurse_triage"}))
        assert result.strip() == "Nurse"


class PendingEscalationCountTest(TestCase):
    """Test that dashboard view includes pending_escalation_count in context."""

    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test Hospital", code=_code())
        self.clin_user = User.objects.create_user(
            username="dr_esc_count",
            password="testpass",  # pragma: allowlist secret
            role="clinician",
        )
        self.clinician = Clinician.objects.create(
            user=self.clin_user,
            role="physician",
            is_active=True,
        )
        self.clinician.hospitals.add(self.hospital)
        self.client.login(username="dr_esc_count", password="testpass")  # pragma: allowlist secret

    def test_dashboard_has_pending_escalation_count(self):
        response = self.client.get("/clinician/dashboard/")
        assert response.status_code == 200
        assert "pending_escalation_count" in response.context
        assert response.context["pending_escalation_count"] == 0

    def test_dashboard_counts_pending_escalations(self):
        pat_user = User.objects.create_user(
            username="pat_esc",
            password="testpass",  # pragma: allowlist secret
            role="patient",
        )
        patient = Patient.objects.create(
            user=pat_user,
            hospital=self.hospital,
            leaflet_code=_lc(),
            date_of_birth="1960-01-15",
        )
        Escalation.objects.create(
            patient=patient,
            severity="critical",
            status="pending",
            reason="chest pain",
        )
        Escalation.objects.create(
            patient=patient,
            severity="urgent",
            status="resolved",
            reason="already resolved",
        )

        response = self.client.get("/clinician/dashboard/")
        assert response.context["pending_escalation_count"] == 1


class SeedDemoDataCommandTest(TestCase):
    """Test the seed_demo_data management command."""

    def setUp(self):
        # Create prerequisites
        call_command("seed_instruments", verbosity=0)
        Hospital.objects.create(name="St. Jude Medical Center", code="SJMC")

    def test_creates_margaret_torres(self):
        call_command("seed_demo_data", verbosity=0)
        assert Patient.objects.filter(user__username="margaret_torres").exists()
        patient = Patient.objects.get(user__username="margaret_torres")
        assert patient.surgery_type == "CABG"
        assert patient.status == "yellow"
        assert patient.leaflet_code == "DEMO-MARGARET"

    def test_creates_survey_instances(self):
        # Need at least one named patient for surveys
        pat_user = User.objects.create_user(
            username="robert_chen_test",
            password="testpass",  # pragma: allowlist secret
            role="patient",
            first_name="Robert",
            last_name="Chen",
        )
        hospital = Hospital.objects.get(code="SJMC")
        Patient.objects.create(
            user=pat_user,
            hospital=hospital,
            leaflet_code=_lc(),
            date_of_birth="1960-01-15",
        )

        call_command("seed_demo_data", verbosity=0)

        # Robert Chen should have survey data
        assert SurveyInstance.objects.filter(
            patient__user__first_name="Robert",
            patient__user__last_name="Chen",
            status="completed",
        ).exists()

    def test_creates_daily_metrics(self):
        call_command("seed_demo_data", verbosity=0)
        # 91 days * 2 rows each (hospital + aggregate)
        assert DailyMetrics.objects.count() >= 180

    def test_margaret_has_pending_survey(self):
        call_command("seed_demo_data", verbosity=0)
        patient = Patient.objects.get(user__username="margaret_torres")
        pending = SurveyInstance.objects.filter(
            patient=patient,
            status="available",
        )
        assert pending.exists()

    def test_idempotent(self):
        """Running twice doesn't fail or duplicate."""
        call_command("seed_demo_data", verbosity=0)
        call_command("seed_demo_data", verbosity=0)
        # Margaret should still exist once
        assert Patient.objects.filter(user__username="margaret_torres").count() == 1


class ResetDemoCommandTest(TestCase):
    """Test that reset_demo runs without errors on a clean DB."""

    def test_reset_demo_runs(self):
        # This will fail if any seed command has missing dependencies
        # or if the ordering is wrong
        call_command("reset_demo", verbosity=0)
        # Basic sanity: patients exist
        assert Patient.objects.count() > 0
        # DailyMetrics exist
        assert DailyMetrics.objects.count() > 0
        # Margaret Torres exists
        assert Patient.objects.filter(user__username="margaret_torres").exists()
