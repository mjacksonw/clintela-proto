"""Tests for SurveyService business logic."""

from datetime import date, timedelta
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.agents.models import AgentConversation, AgentMessage
from apps.patients.models import Hospital, Patient
from apps.surveys.models import (
    SurveyAnswer,
    SurveyAssignment,
    SurveyInstance,
    SurveyInstrument,
)
from apps.surveys.services import SurveyService


class SurveyServiceTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(name="Test Hospital", code="TST")
        cls.user = User.objects.create_user(
            username="svc_patient",
            password="testpass",  # pragma: allowlist secret
            role="patient",
        )
        cls.patient = Patient.objects.create(
            user=cls.user,
            hospital=cls.hospital,
            date_of_birth=date(1960, 1, 1),
        )
        # Seed PHQ-2 instrument
        from django.core.management import call_command

        call_command("seed_instruments", verbosity=0)

        cls.instrument = SurveyInstrument.objects.get(code="phq_2")


class CreateAssignmentTest(SurveyServiceTestBase):
    def test_create_assignment_basic(self):
        assignment = SurveyService.create_assignment(
            patient=self.patient,
            instrument_code="phq_2",
            schedule_type="weekly",
        )
        self.assertEqual(assignment.instrument.code, "phq_2")
        self.assertEqual(assignment.schedule_type, "weekly")
        self.assertTrue(assignment.is_active)
        self.assertEqual(assignment.start_date, date.today())

    def test_create_assignment_daily_creates_instance(self):
        assignment = SurveyService.create_assignment(
            patient=self.patient,
            instrument_code="phq_2",
            schedule_type="daily",
        )
        instances = SurveyInstance.objects.filter(assignment=assignment)
        self.assertEqual(instances.count(), 1)
        self.assertEqual(instances.first().status, "available")

    def test_create_assignment_with_custom_escalation(self):
        config = {"total": {"threshold": 2, "severity": "critical"}}
        assignment = SurveyService.create_assignment(
            patient=self.patient,
            instrument_code="phq_2",
            schedule_type="weekly",
            escalation_config=config,
        )
        self.assertEqual(assignment.escalation_config, config)

    def test_create_assignment_uses_instrument_defaults(self):
        assignment = SurveyService.create_assignment(
            patient=self.patient,
            instrument_code="phq_2",
            schedule_type="weekly",
        )
        self.assertIn("total", assignment.escalation_config)


class CreateInstanceTest(SurveyServiceTestBase):
    def setUp(self):
        self.assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )

    def test_create_instance(self):
        instance = SurveyService.create_instance_for_assignment(self.assignment)
        self.assertIsNotNone(instance)
        self.assertEqual(instance.status, "available")
        self.assertEqual(instance.patient, self.patient)

    def test_no_duplicate_active_instance(self):
        SurveyService.create_instance_for_assignment(self.assignment)
        second = SurveyService.create_instance_for_assignment(self.assignment)
        self.assertIsNone(second)

    def test_weekly_window(self):
        self.assignment.schedule_type = "weekly"
        self.assignment.save()
        instance = SurveyService.create_instance_for_assignment(self.assignment)
        self.assertIsNotNone(instance)
        # Window should span ~7 days
        delta = instance.window_end - instance.window_start
        self.assertAlmostEqual(delta.days, 7, delta=1)

    def test_monthly_window(self):
        self.assignment.schedule_type = "monthly"
        self.assignment.save()
        instance = SurveyService.create_instance_for_assignment(self.assignment)
        self.assertIsNotNone(instance)

    def test_concurrent_creation_handled(self):
        """IntegrityError from concurrent creation is caught gracefully."""
        with patch.object(SurveyInstance.objects, "create", side_effect=IntegrityError("duplicate")):
            result = SurveyService.create_instance_for_assignment(self.assignment)
            self.assertIsNone(result)


class StartAndCompleteTest(SurveyServiceTestBase):
    def setUp(self):
        self.assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )
        now = timezone.now()
        self.instance = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="available",
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
        )
        # Create conversation for chat injection
        self.conversation = AgentConversation.objects.create(
            patient=self.patient,
            status="active",
        )

    def test_start_instance(self):
        result = SurveyService.start_instance(self.instance)
        self.assertEqual(result.status, "in_progress")
        self.assertIsNotNone(result.started_at)

    def test_save_answers(self):
        self.instance.status = "in_progress"
        self.instance.save()
        questions = self.instrument.questions.all()
        answers = {q.code: 1 for q in questions}
        saved = SurveyService.save_answers(self.instance, answers)
        self.assertEqual(len(saved), questions.count())

    def test_save_answers_update_existing(self):
        """Updating an existing answer uses update_or_create."""
        self.instance.status = "in_progress"
        self.instance.save()
        q = self.instrument.questions.first()
        SurveyService.save_answers(self.instance, {q.code: 1})
        SurveyService.save_answers(self.instance, {q.code: 2})
        answer = SurveyAnswer.objects.get(instance=self.instance, question=q)
        self.assertEqual(answer.value, 2)

    def test_save_answers_ignores_unknown_codes(self):
        self.instance.status = "in_progress"
        self.instance.save()
        saved = SurveyService.save_answers(self.instance, {"nonexistent": 5})
        self.assertEqual(len(saved), 0)

    def test_complete_instance_scores(self):
        self.instance.status = "in_progress"
        self.instance.save()
        # Save answers
        for q in self.instrument.questions.all():
            SurveyAnswer.objects.create(instance=self.instance, question=q, value=1)

        result = SurveyService.complete_instance(self.instance)
        self.assertEqual(result.status, "completed")
        self.assertIsNotNone(result.completed_at)
        self.assertEqual(result.total_score, 2.0)  # interest=1 + depressed=1
        self.assertFalse(result.scoring_error)

    def test_complete_instance_injects_chat_message(self):
        self.instance.status = "in_progress"
        self.instance.save()
        for q in self.instrument.questions.all():
            SurveyAnswer.objects.create(instance=self.instance, question=q, value=0)

        SurveyService.complete_instance(self.instance)
        system_msgs = AgentMessage.objects.filter(conversation=self.conversation, role="system")
        self.assertEqual(system_msgs.count(), 1)
        msg = system_msgs.first()
        self.assertEqual(msg.metadata["type"], "survey_completed")

    def test_complete_instance_escalation(self):
        """Score >= 3 triggers escalation for PHQ-2."""
        self.instance.status = "in_progress"
        self.instance.save()
        for q in self.instrument.questions.all():
            SurveyAnswer.objects.create(instance=self.instance, question=q, value=2)

        result = SurveyService.complete_instance(self.instance)
        self.assertEqual(result.total_score, 4.0)
        self.assertTrue(result.escalation_triggered)

    def test_complete_instance_scoring_error(self):
        """If scoring fails, instance is still completed with scoring_error=True."""
        self.instance.status = "in_progress"
        self.instance.save()
        # No answers saved — scoring will use empty dict, should still work
        # but let's mock a failure
        with patch(
            "apps.surveys.services.ScoringEngine.score_instance",
            side_effect=Exception("boom"),
        ):
            result = SurveyService.complete_instance(self.instance)
            self.assertEqual(result.status, "completed")
            self.assertTrue(result.scoring_error)


class MissedMessageTest(SurveyServiceTestBase):
    def test_inject_missed_message(self):
        assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )
        now = timezone.now()
        instance = SurveyInstance.objects.create(
            assignment=assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="missed",
            due_date=date.today(),
            window_start=now - timedelta(days=1),
            window_end=now,
        )
        AgentConversation.objects.create(patient=self.patient, status="active")

        SurveyService.inject_missed_message(instance)
        msg = AgentMessage.objects.filter(role="system").first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.metadata["type"], "survey_missed")


class ScoreChangeAlertTest(SurveyServiceTestBase):
    def setUp(self):
        self.assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )
        now = timezone.now()
        # First completion
        self.prev = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="completed",
            due_date=date.today() - timedelta(days=1),
            window_start=now - timedelta(days=2),
            window_end=now - timedelta(days=1),
            completed_at=now - timedelta(days=1),
            total_score=1.0,
        )

    def test_no_alert_on_first_completion(self):
        """First completion has no previous — no alert."""
        self.prev.delete()
        now = timezone.now()
        instance = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="completed",
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
            completed_at=now,
            total_score=3.0,
        )
        # Should not raise
        SurveyService._check_score_change_alert(instance)

    def test_alert_on_significant_increase(self):
        """PHQ-2 alerts on delta >= 2 increase."""
        now = timezone.now()
        instance = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="completed",
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
            completed_at=now,
            total_score=4.0,  # delta = 3 from prev score 1
        )
        with patch.object(SurveyService, "_send_clinician_alert") as mock:
            SurveyService._check_score_change_alert(instance)
            mock.assert_called_once()


class HelperMethodsTest(SurveyServiceTestBase):
    def test_get_available_surveys_empty(self):
        result = SurveyService.get_available_surveys(self.patient)
        self.assertEqual(len(result), 0)

    def test_get_next_survey_date_none(self):
        result = SurveyService.get_next_survey_date(self.patient)
        self.assertIsNone(result)

    def test_get_score_history_empty(self):
        result = SurveyService.get_score_history(self.patient)
        self.assertEqual(len(result), 0)

    def test_get_max_score(self):
        self.assertEqual(SurveyService._get_max_score("phq_2"), 6)
        self.assertEqual(SurveyService._get_max_score("kccq_12"), 100)
        self.assertIsNone(SurveyService._get_max_score("nonexistent"))

    def test_get_available_surveys_returns_sorted(self):
        """Surveys sorted by estimated_minutes ascending."""
        daily = SurveyInstrument.objects.get(code="daily_symptom")
        kccq = SurveyInstrument.objects.get(code="kccq_12")
        now = timezone.now()
        for inst in [kccq, daily]:
            a = SurveyAssignment.objects.create(
                patient=self.patient, instrument=inst, schedule_type="daily", start_date=date.today()
            )
            SurveyInstance.objects.create(
                assignment=a,
                patient=self.patient,
                instrument=inst,
                status="available",
                due_date=date.today(),
                window_start=now,
                window_end=now + timedelta(days=1),
            )
        result = SurveyService.get_available_surveys(self.patient)
        self.assertEqual(len(result), 2)
        # Daily (2 min) should come before KCCQ (8 min)
        self.assertLessEqual(
            result[0].instrument.estimated_minutes,
            result[1].instrument.estimated_minutes,
        )


class AutoAssignFromPathwayTest(SurveyServiceTestBase):
    def test_auto_assign_with_no_defaults(self):
        """No survey_defaults in pathway metadata — no assignments created."""
        from apps.pathways.models import ClinicalPathway, PatientPathway

        pathway = ClinicalPathway.objects.create(
            name="Test Pathway", surgery_type="Test", description="test", duration_days=30
        )
        pp = PatientPathway.objects.create(patient=self.patient, pathway=pathway)
        SurveyService.auto_assign_from_pathway(pp)
        self.assertEqual(SurveyAssignment.objects.filter(patient=self.patient).count(), 0)
