"""Tests for RecoveryTimelineService — patient-facing recovery timeline."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.agents.tests.factories import PatientFactory
from apps.clinical.models import ClinicalAlert
from apps.pathways.models import (
    ClinicalPathway,
    PathwayMilestone,
    PatientMilestoneCheckin,
    PatientPathway,
)
from apps.patients.services import RecoveryTimelineService


@pytest.fixture
def patient(db):
    return PatientFactory(surgery_date=date.today() - timedelta(days=10))


@pytest.fixture
def pathway(db):
    return ClinicalPathway.objects.create(
        name="CABG Recovery",
        surgery_type="CABG",
        description="Post-CABG recovery pathway",
        duration_days=30,
    )


@pytest.fixture
def milestones(pathway):
    """Create milestones at days 1, 7, 14, 30."""
    days = [
        (1, "early", "Day 1: Welcome Home", "First day home from hospital"),
        (7, "early", "Day 7: One Week Check-in", "One week post-surgery"),
        (14, "middle", "Day 14: Two Week Milestone", "Two weeks of recovery"),
        (30, "late", "Day 30: One Month Review", "One month milestone"),
    ]
    result = []
    for day, phase, title, desc in days:
        result.append(
            PathwayMilestone.objects.create(pathway=pathway, day=day, phase=phase, title=title, description=desc)
        )
    return result


@pytest.fixture
def patient_pathway(patient, pathway):
    return PatientPathway.objects.create(patient=patient, pathway=pathway, status="active")


class TestRecoveryTimelineService:
    def test_timeline_with_milestones(self, patient, patient_pathway, milestones):
        """Pathway with milestones returns timeline events."""
        timeline = RecoveryTimelineService.get_timeline(patient)
        milestone_events = [e for e in timeline if e["type"] == "milestone"]
        assert len(milestone_events) == 4

    def test_timeline_milestone_statuses(self, patient, patient_pathway, milestones):
        """Completed/current/upcoming statuses correctly determined.

        Patient is 10 days post-op, so day 1 and 7 are current, day 14 and 30 are upcoming.
        """
        # Complete day 1
        PatientMilestoneCheckin.objects.create(
            patient=patient,
            milestone=milestones[0],
            completed_at=timezone.now() - timedelta(days=9),
        )

        timeline = RecoveryTimelineService.get_timeline(patient)
        milestone_events = [e for e in timeline if e["type"] == "milestone"]

        statuses = {e["day"]: e["status"] for e in milestone_events}
        assert statuses[1] == "completed"
        assert statuses[7] == "current"  # day 7 <= 10 days post-op
        assert statuses[14] == "upcoming"  # day 14 > 10 days post-op
        assert statuses[30] == "upcoming"

    def test_timeline_warm_messages(self, patient, patient_pathway, milestones):
        """Day 1, 7, 14, 30 milestones get warm messages."""
        timeline = RecoveryTimelineService.get_timeline(patient)
        milestone_events = {e["day"]: e for e in timeline if e["type"] == "milestone"}

        assert milestone_events[1]["warm_message"] != ""
        assert milestone_events[7]["warm_message"] != ""
        assert milestone_events[14]["warm_message"] != ""
        assert milestone_events[30]["warm_message"] != ""

    def test_timeline_empty_no_pathway(self, patient):
        """Patient without a pathway returns empty list."""
        timeline = RecoveryTimelineService.get_timeline(patient)
        assert timeline == []

    def test_timeline_includes_alerts(self, patient, patient_pathway, milestones):
        """Clinical alerts appear in the timeline."""
        ClinicalAlert.objects.create(
            patient=patient,
            alert_type="threshold",
            severity="warning",
            rule_name="test_alert",
            title="Weight increase",
            description="Weight increased over 3 days",
        )
        timeline = RecoveryTimelineService.get_timeline(patient)
        alert_events = [e for e in timeline if e["type"] == "alert"]
        assert len(alert_events) == 1
        assert alert_events[0]["title"] == "Weight increase"

    def test_timeline_chronological_order(self, patient, patient_pathway, milestones):
        """Events sorted by day."""
        timeline = RecoveryTimelineService.get_timeline(patient)
        days = [e["day"] for e in timeline]
        assert days == sorted(days)


class TestRecoveryTimelineView:
    def test_timeline_view_returns_200(self, client, patient, patient_pathway, milestones):
        """HTMX fragment returns 200 for authenticated patient."""
        session = client.session
        session["patient_id"] = patient.pk
        session["authenticated"] = True
        session.save()

        response = client.get("/patient/timeline/")
        assert response.status_code == 200

    def test_timeline_view_unauthenticated(self, client):
        """Returns empty response for unauthenticated request."""
        response = client.get("/patient/timeline/")
        # View returns empty HttpResponse("") when no patient
        assert response.status_code == 200
        assert response.content == b""
