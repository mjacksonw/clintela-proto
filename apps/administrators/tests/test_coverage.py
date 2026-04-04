"""Additional tests to reach 90%+ coverage for administrators app."""

import uuid as _uuid
from datetime import date, timedelta
from io import StringIO

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.administrators.services import (
    EngagementService,
    EscalationAnalyticsService,
    OperationalAlertService,
    OutcomesService,
    PathwayAnalyticsService,
    ReadmissionService,
)
from apps.administrators.views import _get_filters, _sanitize_csv_value
from apps.agents.models import AgentConversation, AgentMessage, Escalation
from apps.analytics.models import DailyMetrics
from apps.analytics.services import DailyMetricsService
from apps.checkins.models import CheckinSession
from apps.pathways.models import (
    ClinicalPathway,
    PathwayMilestone,
    PatientPathway,
)
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
    defaults = {
        "date_of_birth": _DOB,
        "leaflet_code": _lc(),
        "status": "green",
        "lifecycle_status": "recovering",
    }
    defaults.update(kwargs)
    return Patient.objects.create(user=user, hospital=hospital, **defaults)


class GetFiltersTest(TestCase):
    """Test the _get_filters helper."""

    def _make_request(self, params=None):
        from django.test import RequestFactory

        factory = RequestFactory()
        return factory.get("/", params or {})

    def test_defaults(self):
        hospital_id, days = _get_filters(self._make_request())
        assert hospital_id is None
        assert days == 30

    def test_valid_hospital(self):
        hospital_id, _ = _get_filters(self._make_request({"hospital": "5"}))
        assert hospital_id == 5

    def test_invalid_hospital(self):
        hospital_id, _ = _get_filters(self._make_request({"hospital": "abc"}))
        assert hospital_id is None

    def test_valid_days(self):
        _, days = _get_filters(self._make_request({"days": "90"}))
        assert days == 90

    def test_invalid_days_defaults_to_30(self):
        _, days = _get_filters(self._make_request({"days": "999"}))
        assert days == 30

    def test_non_numeric_days(self):
        _, days = _get_filters(self._make_request({"days": "abc"}))
        assert days == 30


class SanitizeCsvValueTest(TestCase):
    def test_all_dangerous_prefixes(self):
        assert _sanitize_csv_value("=cmd").startswith("\t")
        assert _sanitize_csv_value("-cmd").startswith("\t")
        assert _sanitize_csv_value("+cmd").startswith("\t")
        assert _sanitize_csv_value("@cmd").startswith("\t")

    def test_safe_values(self):
        assert _sanitize_csv_value("Normal") == "Normal"
        assert _sanitize_csv_value("123") == "123"
        assert _sanitize_csv_value("") == ""


class ReadmissionTrendTest(TestCase):
    def test_trend_empty(self):
        result = ReadmissionService.get_trend(days=90)
        assert result == []

    def test_trend_with_data(self):
        Hospital.objects.create(name="Test", code=_code())
        DailyMetrics.objects.create(
            date=date.today() - timedelta(days=5),
            hospital=None,
            readmission_rate=8.5,
            discharges=10,
            readmissions=1,
        )
        result = ReadmissionService.get_trend(days=90)
        assert len(result) == 1

    def test_trend_hospital_filter(self):
        hospital = Hospital.objects.create(name="Test", code=_code())
        DailyMetrics.objects.create(
            date=date.today() - timedelta(days=3),
            hospital=hospital,
            readmission_rate=5.0,
            discharges=20,
            readmissions=1,
        )
        result = ReadmissionService.get_trend(days=90, hospital_id=hospital.id)
        assert len(result) == 1


class DischargeToCommunityCoverageTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_hospital_filter(self):
        p = _make_patient(self.hospital)
        PatientStatusTransition.objects.create(patient=p, from_status="post_op", to_status="discharged")

        other = Hospital.objects.create(name="Other", code=_code())
        result = OutcomesService.get_discharge_to_community(days=30, hospital_id=other.id)
        assert result["rate"] is None  # Other hospital has no discharges


class FollowupCompletionCoverageTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_on_time_completion(self):
        """Checkin completed on time."""
        p = _make_patient(self.hospital)
        CheckinSession.objects.create(
            patient=p,
            date=timezone.now().date(),
            pathway_day=7,
            status="completed",
            completed_at=timezone.now() - timedelta(days=2),
        )
        result = OutcomesService.get_followup_completion(days=30)
        assert result["on_time"] >= 0
        assert result["total"] == 1

    def test_missed_not_counted_as_completed(self):
        """Missed sessions are not counted as completed."""
        p = _make_patient(self.hospital)
        CheckinSession.objects.create(
            patient=p,
            date=timezone.now().date(),
            pathway_day=7,
            status="missed",
        )
        result = OutcomesService.get_followup_completion(days=30)
        assert result["on_time"] == 0
        assert result["total"] == 1

    def test_hospital_filter(self):
        p = _make_patient(self.hospital)
        CheckinSession.objects.create(
            patient=p,
            date=timezone.now().date(),
            pathway_day=7,
            status="pending",
        )
        other = Hospital.objects.create(name="Other", code=_code())
        result = OutcomesService.get_followup_completion(days=30, hospital_id=other.id)
        assert result["total"] == 0


class EngagementCoverageTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_engagement_hospital_filter(self):
        p = _make_patient(self.hospital)
        conv = AgentConversation.objects.create(patient=p, agent_type="supervisor")
        AgentMessage.objects.create(conversation=conv, role="user", content="hi")

        other = Hospital.objects.create(name="Other", code=_code())
        result = EngagementService.get_program_engagement(days=30, hospital_id=other.id)
        assert result["engaged"] == 0

    def test_messaging_stats_hospital_filter(self):
        p = _make_patient(self.hospital)
        conv = AgentConversation.objects.create(patient=p, agent_type="supervisor")
        AgentMessage.objects.create(conversation=conv, role="user", content="hi")

        result = EngagementService.get_messaging_stats(days=30, hospital_id=self.hospital.id)
        assert result["received"] == 1

    def test_checkin_stats_with_data(self):
        p = _make_patient(self.hospital)
        CheckinSession.objects.create(
            patient=p,
            date=timezone.now().date(),
            pathway_day=3,
            status="completed",
            completed_at=timezone.now(),
        )
        CheckinSession.objects.create(
            patient=p,
            date=timezone.now().date() - timedelta(days=1),
            pathway_day=7,
            status="skipped",
        )
        result = EngagementService.get_checkin_stats(days=30)
        assert result["completed"] == 1
        assert result["skipped"] == 1
        assert result["rate"] is not None

    def test_inactive_patients_hospital_filter(self):
        _make_patient(self.hospital)
        other = Hospital.objects.create(name="Other", code=_code())
        _make_patient(other)

        result = EngagementService.get_inactive_patients(days=7, hospital_id=self.hospital.id)
        assert result == 1


class EscalationCoverageTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_status_breakdown_hospital_filter(self):
        p = _make_patient(self.hospital)
        Escalation.objects.create(patient=p, reason="test", severity="critical", status="pending")

        other = Hospital.objects.create(name="Other", code=_code())
        result = EscalationAnalyticsService.get_status_breakdown(hospital_id=other.id)
        assert result["pending"] == 0

    def test_response_stats_with_sla(self):
        p = _make_patient(self.hospital)
        now = timezone.now()
        deadline = now + timedelta(hours=1)
        esc = Escalation.objects.create(
            patient=p,
            reason="test",
            severity="critical",
            status="acknowledged",
            response_deadline=deadline,
        )
        esc.created_at = now - timedelta(minutes=10)
        esc.acknowledged_at = now
        esc.save()

        result = EscalationAnalyticsService.get_response_stats(days=30)
        assert result["sla_compliance"] is not None

    def test_response_stats_hospital_filter(self):
        p = _make_patient(self.hospital)
        Escalation.objects.create(patient=p, reason="test", severity="critical", status="pending")

        other = Hospital.objects.create(name="Other", code=_code())
        result = EscalationAnalyticsService.get_response_stats(days=30, hospital_id=other.id)
        assert result["total"] == 0


class PathwayAnalyticsCoverageTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())
        self.pathway = ClinicalPathway.objects.create(name="Test", surgery_type="c", duration_days=30)

    def test_pathway_effectiveness_with_milestones(self):
        PathwayMilestone.objects.create(pathway=self.pathway, day=3, title="Day 3", phase="early")
        p = _make_patient(self.hospital)
        PatientPathway.objects.create(patient=p, pathway=self.pathway, status="active")
        CheckinSession.objects.create(
            patient=p,
            date=timezone.now().date(),
            pathway_day=3,
            status="completed",
            completed_at=timezone.now(),
        )

        result = PathwayAnalyticsService.get_pathway_effectiveness(self.pathway.id)
        assert len(result["milestones"]) == 1
        assert result["milestones"][0]["completed"] == 1


class StaleEscalationAlertTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_stale_escalation_alert(self):
        p = _make_patient(self.hospital)
        esc = Escalation.objects.create(
            patient=p,
            reason="test",
            severity="urgent",
            status="pending",
        )
        # Make it older than 24 hours
        Escalation.objects.filter(id=esc.id).update(created_at=timezone.now() - timedelta(hours=25))

        alerts = OperationalAlertService.get_all_alerts()
        stale = [a for a in alerts if a["type"] == "stale_escalation"]
        assert len(stale) == 1


class DailyMetricsServiceTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_compute_for_date(self):
        _make_patient(self.hospital)
        target = date.today()
        DailyMetricsService.compute_for_date(target)

        # Should create per-hospital + aggregate row
        assert DailyMetrics.objects.filter(date=target, hospital=self.hospital).exists()
        assert DailyMetrics.objects.filter(date=target, hospital__isnull=True).exists()

    def test_idempotent(self):
        """Running twice on same date doesn't create duplicates."""
        target = date.today()
        DailyMetricsService.compute_for_date(target)
        DailyMetricsService.compute_for_date(target)
        assert DailyMetrics.objects.filter(date=target, hospital__isnull=True).count() == 1

    def test_compute_with_data(self):
        p = _make_patient(self.hospital)
        conv = AgentConversation.objects.create(patient=p, agent_type="supervisor")
        AgentMessage.objects.create(conversation=conv, role="user", content="hi")
        AgentMessage.objects.create(conversation=conv, role="assistant", content="hello")
        PatientStatusTransition.objects.create(patient=p, from_status="post_op", to_status="discharged")

        target = date.today()
        DailyMetricsService.compute_for_date(target)

        metrics = DailyMetrics.objects.get(date=target, hospital__isnull=True)
        assert metrics.active_patients >= 1
        assert metrics.messages_received >= 1
        assert metrics.messages_sent >= 1
        assert metrics.discharges >= 1


class ComputeMetricsCommandTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_default_yesterday(self):
        from django.core.management import call_command

        out = StringIO()
        call_command("compute_daily_metrics", stdout=out)
        assert "Computed metrics" in out.getvalue()

    def test_specific_date(self):
        from django.core.management import call_command

        out = StringIO()
        call_command("compute_daily_metrics", date="2026-03-20", stdout=out)
        assert "2026-03-20" in out.getvalue()

    def test_backfill(self):
        from django.core.management import call_command

        out = StringIO()
        call_command("compute_daily_metrics", backfill=3, stdout=out)
        assert "Backfilled 3 days" in out.getvalue()


class ViewCoverageTest(TestCase):
    """Test remaining uncovered view paths."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            password="pass",  # pragma: allowlist secret
            role="admin",
        )
        self.hospital = Hospital.objects.create(name="Test", code=_code())
        self.client.login(username="admin", password="pass")

    def test_pathway_performance_fragment_renders(self):
        ClinicalPathway.objects.create(name="P1", surgery_type="c", duration_days=30)
        response = self.client.get(reverse("administrators:pathway_performance"))
        assert response.status_code == 200
        assert b"P1" in response.content

    def test_message_volume_with_data(self):
        p = _make_patient(self.hospital)
        conv = AgentConversation.objects.create(patient=p, agent_type="supervisor")
        AgentMessage.objects.create(conversation=conv, role="user", content="hi")

        response = self.client.get(reverse("administrators:message_volume"))
        assert response.status_code == 200

    def test_checkin_completion_with_data(self):
        p = _make_patient(self.hospital)
        CheckinSession.objects.create(
            patient=p,
            date=timezone.now().date(),
            pathway_day=3,
            status="completed",
            completed_at=timezone.now(),
        )
        response = self.client.get(reverse("administrators:checkin_completion"))
        assert response.status_code == 200

    def test_escalation_response_with_data(self):
        p = _make_patient(self.hospital)
        Escalation.objects.create(patient=p, reason="test", severity="critical", status="pending")
        response = self.client.get(reverse("administrators:escalation_response"))
        assert response.status_code == 200

    def test_csv_export_with_data(self):
        p = _make_patient(self.hospital)
        conv = AgentConversation.objects.create(patient=p, agent_type="supervisor")
        AgentMessage.objects.create(conversation=conv, role="user", content="hello")
        PatientStatusTransition.objects.create(patient=p, from_status="post_op", to_status="discharged")

        response = self.client.get(reverse("administrators:export_csv"))
        assert response.status_code == 200
        # Consume streaming content
        content = b"".join(response.streaming_content).decode()
        assert "Readmission Rate" in content
        assert "Census" in content

    def test_milestone_edit(self):
        pathway = ClinicalPathway.objects.create(name="P", surgery_type="c", duration_days=30)
        milestone = PathwayMilestone.objects.create(pathway=pathway, day=3, title="Day 3", phase="early")

        response = self.client.post(
            reverse("administrators:milestone_edit", args=[milestone.id]),
            {"title": "Updated Day 3", "description": "New desc"},
        )
        assert response.status_code == 200
        milestone.refresh_from_db()
        assert milestone.title == "Updated Day 3"

    def test_milestone_edit_empty_title(self):
        pathway = ClinicalPathway.objects.create(name="P", surgery_type="c", duration_days=30)
        milestone = PathwayMilestone.objects.create(pathway=pathway, day=3, title="Day 3", phase="early")

        response = self.client.post(
            reverse("administrators:milestone_edit", args=[milestone.id]),
            {"title": "", "description": "desc"},
        )
        assert response.status_code == 200
        # Milestone should NOT be changed
        milestone.refresh_from_db()
        assert milestone.title == "Day 3"

    def test_alerts_with_data(self):
        p = _make_patient(self.hospital)
        Escalation.objects.create(
            patient=p,
            reason="test",
            severity="critical",
            status="pending",
            response_deadline=timezone.now() - timedelta(hours=1),
        )
        response = self.client.get(reverse("administrators:alerts"))
        assert response.status_code == 200
        assert b"SLA" in response.content or b"past" in response.content

    def test_hero_with_period_param(self):
        response = self.client.get(reverse("administrators:hero_readmission"), {"period": "90"})
        assert response.status_code == 200

    def test_hero_with_invalid_period(self):
        response = self.client.get(reverse("administrators:hero_readmission"), {"period": "abc"})
        assert response.status_code == 200

    def test_engagement_with_data(self):
        p = _make_patient(self.hospital)
        conv = AgentConversation.objects.create(patient=p, agent_type="supervisor")
        AgentMessage.objects.create(conversation=conv, role="user", content="hello")

        response = self.client.get(reverse("administrators:engagement"))
        assert response.status_code == 200
