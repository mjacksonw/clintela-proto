"""Tests for survey models."""

import uuid
from datetime import date, timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.patients.models import Hospital, Patient
from apps.surveys.models import (
    SurveyAnswer,
    SurveyAssignment,
    SurveyInstance,
    SurveyInstrument,
    SurveyQuestion,
)


class SurveyModelTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(name="Test Hospital", code="TST")
        cls.user = User.objects.create_user(
            username="patient1",
            password="testpass",  # pragma: allowlist secret
            role="patient",
        )
        cls.patient = Patient.objects.create(
            user=cls.user,
            hospital=cls.hospital,
            date_of_birth=date(1960, 1, 1),
        )
        cls.instrument = SurveyInstrument.objects.create(
            code="test_survey",
            name="Test Survey",
            category="general",
            estimated_minutes=5,
        )
        cls.question = SurveyQuestion.objects.create(
            instrument=cls.instrument,
            code="q1",
            order=1,
            text="How are you?",
            question_type="likert",
            options=[
                {"value": 0, "label": "Bad"},
                {"value": 1, "label": "OK"},
                {"value": 2, "label": "Good"},
            ],
        )


class SurveyInstrumentTest(SurveyModelTestBase):
    def test_str(self):
        self.assertEqual(str(self.instrument), "Test Survey (v1.0)")

    def test_questions_relation(self):
        self.assertEqual(self.instrument.questions.count(), 1)

    def test_unique_code(self):
        with self.assertRaises(IntegrityError):
            SurveyInstrument.objects.create(
                code="test_survey",
                name="Duplicate",
                category="general",
            )


class SurveyQuestionTest(SurveyModelTestBase):
    def test_str(self):
        self.assertIn("test_survey.q1", str(self.question))

    def test_unique_instrument_code(self):
        with self.assertRaises(IntegrityError):
            SurveyQuestion.objects.create(
                instrument=self.instrument,
                code="q1",
                order=2,
                text="Duplicate",
                question_type="likert",
            )


class SurveyAssignmentTest(SurveyModelTestBase):
    def test_create(self):
        assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )
        self.assertTrue(assignment.is_active)
        self.assertEqual(str(assignment), f"{self.patient} — test_survey (daily)")

    def test_unique_active_constraint(self):
        SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )
        with self.assertRaises(IntegrityError):
            SurveyAssignment.objects.create(
                patient=self.patient,
                instrument=self.instrument,
                schedule_type="weekly",
                start_date=date.today(),
            )

    def test_inactive_allows_new(self):
        a1 = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )
        a1.is_active = False
        a1.save()
        # Should not raise
        SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="weekly",
            start_date=date.today(),
        )


class SurveyInstanceTest(SurveyModelTestBase):
    def setUp(self):
        self.assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )

    def test_create(self):
        now = timezone.now()
        instance = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
        )
        self.assertIsInstance(instance.id, uuid.UUID)
        self.assertEqual(instance.status, "pending")
        self.assertFalse(instance.scoring_error)

    def test_one_active_constraint(self):
        now = timezone.now()
        SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="available",
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
        )
        with self.assertRaises(IntegrityError):
            SurveyInstance.objects.create(
                assignment=self.assignment,
                patient=self.patient,
                instrument=self.instrument,
                status="available",
                due_date=date.today() + timedelta(days=1),
                window_start=now + timedelta(days=1),
                window_end=now + timedelta(days=2),
            )

    def test_completed_allows_new(self):
        now = timezone.now()
        i1 = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="available",
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
        )
        i1.status = "completed"
        i1.save()
        # Should not raise
        SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="available",
            due_date=date.today() + timedelta(days=1),
            window_start=now + timedelta(days=1),
            window_end=now + timedelta(days=2),
        )


class SurveyAnswerTest(SurveyModelTestBase):
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
            status="in_progress",
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
        )

    def test_create(self):
        answer = SurveyAnswer.objects.create(
            instance=self.instance,
            question=self.question,
            value=2,
            raw_value="2",
        )
        self.assertEqual(answer.value, 2)

    def test_unique_instance_question(self):
        SurveyAnswer.objects.create(
            instance=self.instance,
            question=self.question,
            value=1,
        )
        with self.assertRaises(IntegrityError):
            SurveyAnswer.objects.create(
                instance=self.instance,
                question=self.question,
                value=2,
            )
