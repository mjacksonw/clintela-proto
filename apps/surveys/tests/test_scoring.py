"""Tests for ScoringEngine."""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.patients.models import Hospital, Patient
from apps.surveys.models import (
    SurveyAnswer,
    SurveyAssignment,
    SurveyInstance,
    SurveyInstrument,
)
from apps.surveys.scoring import ScoringEngine, ScoringResult


class ScoringEngineTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(name="Score Hospital", code="SCH")
        cls.user = User.objects.create_user(
            username="score_patient",
            password="testpass",  # pragma: allowlist secret
            role="patient",
        )
        cls.patient = Patient.objects.create(
            user=cls.user,
            hospital=cls.hospital,
            date_of_birth=date(1960, 1, 1),
        )
        from django.core.management import call_command

        call_command("seed_instruments", verbosity=0)
        cls.instrument = SurveyInstrument.objects.get(code="phq_2")

    def _create_instance_with_answers(self, answers_dict):
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
            status="in_progress",
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
        )
        for code, value in answers_dict.items():
            question = self.instrument.questions.get(code=code)
            SurveyAnswer.objects.create(instance=instance, question=question, value=value)
        return instance

    def test_score_instance(self):
        instance = self._create_instance_with_answers({"interest": 1, "depressed": 2})
        result = ScoringEngine.score_instance(instance)
        self.assertIsInstance(result, ScoringResult)
        self.assertEqual(result.total_score, 3)
        self.assertTrue(result.escalation_needed)

    def test_score_instance_unknown_instrument(self):
        """Unknown instrument code returns None."""
        custom = SurveyInstrument.objects.create(code="custom_unknown", name="Unknown", category="custom")
        assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=custom,
            schedule_type="daily",
            start_date=date.today(),
        )
        now = timezone.now()
        instance = SurveyInstance.objects.create(
            assignment=assignment,
            patient=self.patient,
            instrument=custom,
            status="in_progress",
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
        )
        result = ScoringEngine.score_instance(instance)
        self.assertIsNone(result)

    def test_check_escalation_needed(self):
        instance = self._create_instance_with_answers({"interest": 2, "depressed": 2})
        result = ScoringEngine.score_instance(instance)
        self.assertTrue(ScoringEngine.check_escalation(instance, result))

    def test_check_escalation_not_needed(self):
        instance = self._create_instance_with_answers({"interest": 0, "depressed": 0})
        result = ScoringEngine.score_instance(instance)
        self.assertFalse(ScoringEngine.check_escalation(instance, result))

    def test_check_escalation_uses_assignment_config(self):
        """Assignment escalation config overrides instrument defaults."""
        instance = self._create_instance_with_answers({"interest": 1, "depressed": 0})
        instance.assignment.escalation_config = {"total": {"threshold": 1, "severity": "urgent"}}
        instance.assignment.save()
        # Create a result that says escalation is needed (score >= custom threshold)
        result = ScoringResult(
            total_score=1,
            domain_scores={},
            raw_scores={"interest": 1, "depressed": 0},
            interpretation="test",
            escalation_needed=True,
        )
        self.assertTrue(ScoringEngine.check_escalation(instance, result))

    def test_check_escalation_domain_threshold(self):
        """Domain-level thresholds can trigger escalation."""
        instance = self._create_instance_with_answers({"interest": 0, "depressed": 0})
        result = ScoringResult(
            total_score=0,
            domain_scores={"test_domain": 95},
            raw_scores={},
            interpretation="test",
            escalation_needed=True,
        )
        instance.assignment.escalation_config = {"domains": {"test_domain": {"threshold": 90}}}
        instance.assignment.save()
        self.assertTrue(ScoringEngine.check_escalation(instance, result))
