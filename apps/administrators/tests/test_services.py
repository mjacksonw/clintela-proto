"""Tests for administrator dashboard services."""

import uuid as _uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.administrators.services import (
    CensusService,
    EngagementService,
    EscalationAnalyticsService,
    OperationalAlertService,
    OutcomesService,
    PathwayAnalyticsService,
    ReadmissionService,
)
from apps.agents.models import AgentConversation, AgentMessage, Escalation
from apps.pathways.models import (
    ClinicalPathway,
    PatientPathway,
)
from apps.patients.models import Hospital, Patient, PatientStatusTransition

_DOB = "1960-01-15"


def _code():
    return f"H-{_uuid.uuid4().hex[:8]}"


def _lc():
    return f"LC-{_uuid.uuid4().hex[:8]}"


def _make_patient(hospital, status="green", lifecycle="recovering", **kwargs):
    user = User.objects.create_user(
        username=f"patient_{_uuid.uuid4().hex[:6]}",
        password="pass",  # pragma: allowlist secret
        role="patient",
    )
    return Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth=_DOB,
        leaflet_code=_lc(),
        status=status,
        lifecycle_status=lifecycle,
        **kwargs,
    )


class CensusServiceTest(TestCase):
    def setUp(self):
        self.hospital_a = Hospital.objects.create(name="Hospital A", code=_code())
        self.hospital_b = Hospital.objects.create(name="Hospital B", code=_code())

    def test_population_summary_empty(self):
        result = CensusService.get_population_summary()
        assert result["total"] == 0
        assert result["by_status"] == {}

    def test_population_summary_with_patients(self):
        _make_patient(self.hospital_a, status="green")
        _make_patient(self.hospital_a, status="red")
        _make_patient(self.hospital_b, status="green")

        result = CensusService.get_population_summary()
        assert result["total"] == 3
        assert result["by_status"]["green"] == 2
        assert result["by_status"]["red"] == 1

    def test_population_summary_hospital_filter(self):
        _make_patient(self.hospital_a)
        _make_patient(self.hospital_b)

        result = CensusService.get_population_summary(hospital_id=self.hospital_a.id)
        assert result["total"] == 1

    def test_triage_distribution(self):
        _make_patient(self.hospital_a, status="green")
        _make_patient(self.hospital_a, status="yellow")
        _make_patient(self.hospital_a, status="orange")
        _make_patient(self.hospital_a, status="red")

        result = CensusService.get_triage_distribution()
        assert result["green"] == 1
        assert result["yellow"] == 1
        assert result["orange"] == 1
        assert result["red"] == 1
        assert result["total"] == 4

    def test_hospital_breakdown(self):
        _make_patient(self.hospital_a)
        _make_patient(self.hospital_a)
        _make_patient(self.hospital_b)

        result = CensusService.get_hospital_breakdown()
        assert len(result) == 2
        by_name = {h["name"]: h for h in result}
        assert by_name["Hospital A"]["active_patients"] == 2
        assert by_name["Hospital B"]["active_patients"] == 1

    def test_inactive_patients_excluded(self):
        _make_patient(self.hospital_a, is_active=False)
        _make_patient(self.hospital_a)

        result = CensusService.get_population_summary()
        assert result["total"] == 1


class ReadmissionServiceTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test Hospital", code=_code())

    def test_no_discharges(self):
        result = ReadmissionService.get_cohort_rate(days=30)
        assert result["rate"] is None
        assert result["display"] == "N/A"

    def test_discharges_no_readmissions(self):
        p = _make_patient(self.hospital)
        PatientStatusTransition.objects.create(patient=p, from_status="post_op", to_status="discharged")
        result = ReadmissionService.get_cohort_rate(days=30)
        assert result["rate"] == 0.0
        assert result["discharges"] == 1
        assert result["readmissions"] == 0

    def test_readmission_rate(self):
        for _ in range(10):
            p = _make_patient(self.hospital)
            PatientStatusTransition.objects.create(patient=p, from_status="post_op", to_status="discharged")
        # 2 readmissions
        for p in Patient.objects.all()[:2]:
            PatientStatusTransition.objects.create(patient=p, from_status="recovering", to_status="readmitted")

        result = ReadmissionService.get_cohort_rate(days=30)
        assert result["rate"] == 20.0
        assert result["readmissions"] == 2
        assert result["discharges"] == 10

    def test_hospital_filter(self):
        hospital_b = Hospital.objects.create(name="Other", code=_code())
        p_a = _make_patient(self.hospital)
        p_b = _make_patient(hospital_b)
        PatientStatusTransition.objects.create(patient=p_a, from_status="post_op", to_status="discharged")
        PatientStatusTransition.objects.create(patient=p_b, from_status="post_op", to_status="discharged")

        result = ReadmissionService.get_cohort_rate(days=30, hospital_id=self.hospital.id)
        assert result["discharges"] == 1


class OutcomesServiceTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_discharge_to_community_empty(self):
        result = OutcomesService.get_discharge_to_community(days=30)
        assert result["rate"] is None

    def test_discharge_to_community_rate(self):
        # 3 discharged, 1 readmitted
        for _ in range(3):
            p = _make_patient(self.hospital)
            PatientStatusTransition.objects.create(patient=p, from_status="post_op", to_status="discharged")

        p_readmit = Patient.objects.first()
        PatientStatusTransition.objects.create(patient=p_readmit, from_status="recovering", to_status="readmitted")

        result = OutcomesService.get_discharge_to_community(days=30)
        assert result["rate"] is not None
        assert result["successful"] == 2
        assert result["total"] == 3

    def test_followup_completion_empty(self):
        result = OutcomesService.get_followup_completion(days=30)
        assert result["rate"] is None


class EngagementServiceTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_program_engagement_no_patients(self):
        result = EngagementService.get_program_engagement(days=30)
        assert result["rate"] is None

    def test_program_engagement_with_messages(self):
        p = _make_patient(self.hospital)
        conv = AgentConversation.objects.create(patient=p, agent_type="supervisor")
        AgentMessage.objects.create(conversation=conv, role="user", content="hello")

        result = EngagementService.get_program_engagement(days=30)
        assert result["rate"] == 100.0
        assert result["engaged"] == 1

    def test_agent_messages_dont_count(self):
        """Only patient-initiated messages (role=user) count for engagement."""
        p = _make_patient(self.hospital)
        conv = AgentConversation.objects.create(patient=p, agent_type="supervisor")
        AgentMessage.objects.create(conversation=conv, role="assistant", content="Hi there")

        result = EngagementService.get_program_engagement(days=30)
        assert result["engaged"] == 0

    def test_multi_horizon(self):
        p = _make_patient(self.hospital)
        conv = AgentConversation.objects.create(patient=p, agent_type="supervisor")
        AgentMessage.objects.create(conversation=conv, role="user", content="hello")

        result = EngagementService.get_program_engagement_multi_horizon()
        assert 7 in result
        assert 14 in result
        assert 30 in result
        assert 90 in result

    def test_messaging_stats(self):
        p = _make_patient(self.hospital)
        conv = AgentConversation.objects.create(patient=p, agent_type="supervisor")
        AgentMessage.objects.create(conversation=conv, role="user", content="hello")
        AgentMessage.objects.create(conversation=conv, role="assistant", content="hi")

        result = EngagementService.get_messaging_stats(days=30)
        assert result["total"] == 2
        assert result["sent"] == 1
        assert result["received"] == 1

    def test_checkin_stats_empty(self):
        result = EngagementService.get_checkin_stats(days=30)
        assert result["rate"] is None

    def test_inactive_patients(self):
        _make_patient(self.hospital)
        _make_patient(self.hospital)

        result = EngagementService.get_inactive_patients(days=7)
        assert result == 2


class EscalationAnalyticsServiceTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_status_breakdown_empty(self):
        result = EscalationAnalyticsService.get_status_breakdown()
        assert result["pending"] == 0
        assert result["acknowledged"] == 0
        assert result["resolved"] == 0

    def test_status_breakdown(self):
        p = _make_patient(self.hospital)
        Escalation.objects.create(patient=p, reason="test", severity="critical", status="pending")
        Escalation.objects.create(patient=p, reason="test2", severity="urgent", status="resolved")

        result = EscalationAnalyticsService.get_status_breakdown()
        assert result["pending"] == 1
        assert result["resolved"] == 1

    def test_response_stats_no_escalations(self):
        result = EscalationAnalyticsService.get_response_stats(days=30)
        assert result["avg_minutes"] is None
        assert result["total"] == 0

    def test_response_stats_with_acknowledgment(self):
        p = _make_patient(self.hospital)
        now = timezone.now()
        esc = Escalation.objects.create(patient=p, reason="test", severity="critical", status="acknowledged")
        esc.created_at = now - timedelta(minutes=20)
        esc.acknowledged_at = now
        esc.save()

        result = EscalationAnalyticsService.get_response_stats(days=30)
        assert result["avg_minutes"] is not None
        assert result["avg_minutes"] >= 19  # Allow for rounding


class PathwayAnalyticsServiceTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())
        self.pathway = ClinicalPathway.objects.create(name="Test Pathway", surgery_type="cardiac", duration_days=30)

    def test_pathway_list_empty(self):
        result = PathwayAnalyticsService.get_pathway_list_with_stats()
        assert len(result) == 1  # The pathway exists even with no assignments
        assert result[0]["total_assigned"] == 0

    def test_pathway_with_assignments(self):
        p = _make_patient(self.hospital)
        PatientPathway.objects.create(patient=p, pathway=self.pathway, status="active")

        result = PathwayAnalyticsService.get_pathway_list_with_stats()
        assert result[0]["active_count"] == 1

    def test_pathway_effectiveness(self):
        p1 = _make_patient(self.hospital)
        p2 = _make_patient(self.hospital)
        PatientPathway.objects.create(patient=p1, pathway=self.pathway, status="completed")
        PatientPathway.objects.create(patient=p2, pathway=self.pathway, status="active")

        result = PathwayAnalyticsService.get_pathway_effectiveness(self.pathway.id)
        assert result["total_assigned"] == 2
        assert result["completed"] == 1
        assert result["completion_rate"] == 50.0

    def test_pathway_effectiveness_not_found(self):
        result = PathwayAnalyticsService.get_pathway_effectiveness(9999)
        assert "error" in result


class OperationalAlertServiceTest(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test", code=_code())

    def test_no_alerts(self):
        alerts = OperationalAlertService.get_all_alerts()
        assert len(alerts) == 0

    def test_sla_breach_alert(self):
        p = _make_patient(self.hospital)
        Escalation.objects.create(
            patient=p,
            reason="test",
            severity="critical",
            status="pending",
            response_deadline=timezone.now() - timedelta(hours=1),
        )
        alerts = OperationalAlertService.get_all_alerts()
        sla_alerts = [a for a in alerts if a["type"] == "sla_breach"]
        assert len(sla_alerts) == 1
        assert sla_alerts[0]["severity"] == "critical"

    def test_inactive_patients_alert(self):
        _make_patient(self.hospital)
        alerts = OperationalAlertService.get_all_alerts()
        inactive_alerts = [a for a in alerts if a["type"] == "inactive_patients"]
        assert len(inactive_alerts) == 1

    def test_max_5_alerts(self):
        """Alerts are capped at 5."""
        p = _make_patient(self.hospital)
        # Create enough conditions for many alerts
        for i in range(10):
            Escalation.objects.create(
                patient=p,
                reason=f"test{i}",
                severity="critical",
                status="pending",
                response_deadline=timezone.now() - timedelta(hours=1),
            )
        alerts = OperationalAlertService.get_all_alerts()
        assert len(alerts) <= 5
