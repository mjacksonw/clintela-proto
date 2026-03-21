"""Tests for survey Celery tasks."""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.agents.models import AgentConversation
from apps.patients.models import Hospital, Patient
from apps.surveys.models import SurveyAssignment, SurveyInstance, SurveyInstrument
from apps.surveys.tasks import create_survey_instances, expire_survey_instances


class TaskTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(name="Task Hospital", code="TH")
        cls.user = User.objects.create_user(
            username="task_patient",
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


class CreateInstancesTaskTest(TaskTestBase):
    def test_creates_instances_for_active_assignments(self):
        SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )
        create_survey_instances()
        self.assertEqual(SurveyInstance.objects.filter(patient=self.patient).count(), 1)

    def test_skips_inactive_assignments(self):
        SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
            is_active=False,
        )
        create_survey_instances()
        self.assertEqual(SurveyInstance.objects.filter(patient=self.patient).count(), 0)

    def test_skips_future_start_date(self):
        SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today() + timedelta(days=7),
        )
        create_survey_instances()
        self.assertEqual(SurveyInstance.objects.filter(patient=self.patient).count(), 0)

    def test_skips_past_end_date(self):
        SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() - timedelta(days=1),
        )
        create_survey_instances()
        self.assertEqual(SurveyInstance.objects.filter(patient=self.patient).count(), 0)


class ExpireInstancesTaskTest(TaskTestBase):
    def setUp(self):
        self.assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )
        AgentConversation.objects.create(patient=self.patient, status="active")

    def test_expires_available_past_window(self):
        now = timezone.now()
        instance = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="available",
            due_date=date.today() - timedelta(days=1),
            window_start=now - timedelta(days=2),
            window_end=now - timedelta(hours=1),
        )
        expire_survey_instances()
        instance.refresh_from_db()
        self.assertEqual(instance.status, "missed")

    def test_does_not_expire_within_window(self):
        now = timezone.now()
        instance = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="available",
            due_date=date.today(),
            window_start=now - timedelta(hours=1),
            window_end=now + timedelta(hours=23),
        )
        expire_survey_instances()
        instance.refresh_from_db()
        self.assertEqual(instance.status, "available")

    def test_in_progress_grace_period(self):
        """In-progress instances get a 2-hour grace period after window_end."""
        now = timezone.now()
        # Window ended 1 hour ago — within grace period
        instance = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="in_progress",
            due_date=date.today(),
            window_start=now - timedelta(days=1),
            window_end=now - timedelta(hours=1),
            started_at=now - timedelta(hours=2),
        )
        expire_survey_instances()
        instance.refresh_from_db()
        self.assertEqual(instance.status, "in_progress")  # Still within grace

    def test_in_progress_past_grace_period(self):
        """In-progress instances past grace period are marked missed."""
        now = timezone.now()
        instance = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="in_progress",
            due_date=date.today() - timedelta(days=1),
            window_start=now - timedelta(days=2),
            window_end=now - timedelta(hours=3),  # 3 hours ago > 2-hour grace
            started_at=now - timedelta(hours=4),
        )
        expire_survey_instances()
        instance.refresh_from_db()
        self.assertEqual(instance.status, "missed")

    def test_atomic_update_prevents_overwriting_completed(self):
        """If a patient completes between fetch and update, status stays completed."""
        now = timezone.now()
        instance = SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="completed",  # Already completed
            due_date=date.today() - timedelta(days=1),
            window_start=now - timedelta(days=2),
            window_end=now - timedelta(hours=1),
            completed_at=now,
            total_score=2.0,
        )
        expire_survey_instances()
        instance.refresh_from_db()
        self.assertEqual(instance.status, "completed")  # NOT overwritten to missed


class ConsecutiveMissesTest(TaskTestBase):
    def setUp(self):
        self.assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today() - timedelta(days=10),
        )
        AgentConversation.objects.create(patient=self.patient, status="active")

    def test_escalation_after_3_consecutive_misses(self):
        """3 consecutive missed surveys creates an escalation."""
        from apps.agents.models import Escalation

        now = timezone.now()
        # Create 2 already-missed instances + 1 available that will expire
        for i in range(2):
            SurveyInstance.objects.create(
                assignment=self.assignment,
                patient=self.patient,
                instrument=self.instrument,
                status="missed",
                due_date=date.today() - timedelta(days=3 - i),
                window_start=now - timedelta(days=4 - i),
                window_end=now - timedelta(days=3 - i),
            )
        # One available that's past window — will be marked missed by task
        SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="available",
            due_date=date.today() - timedelta(days=1),
            window_start=now - timedelta(days=2),
            window_end=now - timedelta(hours=1),
        )

        expire_survey_instances()

        # 3rd instance should now be missed
        missed_count = SurveyInstance.objects.filter(patient=self.patient, status="missed").count()
        self.assertEqual(missed_count, 3)

        # Escalation should be created for 3 consecutive misses
        escalations = Escalation.objects.filter(patient=self.patient)
        self.assertTrue(escalations.exists())

    def test_no_escalation_with_fewer_than_3_misses(self):
        from apps.agents.models import Escalation

        now = timezone.now()
        # 1 already missed + 1 available that will expire = only 2 misses
        SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="missed",
            due_date=date.today() - timedelta(days=2),
            window_start=now - timedelta(days=3),
            window_end=now - timedelta(days=2),
        )
        SurveyInstance.objects.create(
            assignment=self.assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="available",
            due_date=date.today() - timedelta(days=1),
            window_start=now - timedelta(days=2),
            window_end=now - timedelta(hours=1),
        )

        expire_survey_instances()

        escalations = Escalation.objects.filter(patient=self.patient)
        self.assertFalse(escalations.exists())
