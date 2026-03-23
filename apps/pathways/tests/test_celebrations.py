"""Tests for MilestoneCompletionService — celebration logic."""

import pytest
from django.utils import timezone

from apps.agents.tests.factories import PatientFactory
from apps.notifications.models import Notification
from apps.pathways.models import (
    ClinicalPathway,
    PathwayMilestone,
    PatientMilestoneCheckin,
)
from apps.pathways.services import MilestoneCompletionService
from apps.patients.models import PatientPreferences


@pytest.fixture
def patient(db):
    return PatientFactory()


@pytest.fixture
def pathway(db):
    return ClinicalPathway.objects.create(name="Recovery", surgery_type="CABG", description="Test", duration_days=30)


@pytest.fixture
def milestone(pathway):
    return PathwayMilestone.objects.create(
        pathway=pathway, day=7, phase="early", title="Day 7 Check-in", description="One week"
    )


@pytest.fixture
def checkin(patient, milestone):
    return PatientMilestoneCheckin.objects.create(patient=patient, milestone=milestone, completed_at=timezone.now())


class TestMilestoneCompletionService:
    def test_celebrate_creates_notification(self, patient, milestone, checkin):
        """Completing a milestone creates a celebration notification."""
        result = MilestoneCompletionService.celebrate(patient, milestone, checkin)
        assert result is not None
        assert isinstance(result, Notification)
        assert result.patient == patient

    def test_celebrate_idempotent(self, patient, milestone, checkin):
        """Calling celebrate twice does not create a duplicate."""
        first = MilestoneCompletionService.celebrate(patient, milestone, checkin)
        second = MilestoneCompletionService.celebrate(patient, milestone, checkin)
        assert first is not None
        assert second is None
        assert Notification.objects.filter(patient=patient, notification_type="celebration").count() == 1

    def test_celebrate_notification_type(self, patient, milestone, checkin):
        """Notification has type='celebration'."""
        result = MilestoneCompletionService.celebrate(patient, milestone, checkin)
        assert result.notification_type == "celebration"
        assert result.severity == "info"

    def test_celebrate_message_with_goals(self, patient, milestone, checkin):
        """Message references recovery_goals when available."""
        PatientPreferences.objects.create(
            patient=patient,
            recovery_goals="Get back to playing with my grandkids",
        )
        result = MilestoneCompletionService.celebrate(patient, milestone, checkin)
        assert result is not None
        assert "what matters most" in result.message.lower()

    def test_celebrate_message_without_goals(self, patient, milestone, checkin):
        """Works without goals — no crash, message still generated."""
        result = MilestoneCompletionService.celebrate(patient, milestone, checkin)
        assert result is not None
        assert len(result.message) > 0
        # Without goals, should not contain the goal suffix
        assert "what matters most" not in result.message.lower()

    def test_celebrate_returns_notification(self, patient, milestone, checkin):
        """Returns the Notification object (not just the message string)."""
        result = MilestoneCompletionService.celebrate(patient, milestone, checkin)
        assert result is not None
        assert "Day 7" in result.title
