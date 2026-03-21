"""Tests for survey views."""

from datetime import date, timedelta

from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.agents.models import AgentConversation
from apps.clinicians.models import Clinician
from apps.patients.models import Hospital, Patient
from apps.surveys.models import SurveyAnswer, SurveyAssignment, SurveyInstance, SurveyInstrument
from apps.surveys.views import available_surveys, complete_survey, score_history, start_survey, submit_answers


class ViewTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(name="View Hospital", code="VH")
        cls.user = User.objects.create_user(
            username="view_patient",
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

    def _make_request(self, method="GET", data=None):
        factory = RequestFactory()
        request = factory.get("/") if method == "GET" else factory.post("/", data=data or {})
        # Set up session auth
        from django.contrib.sessions.backends.db import SessionStore

        request.session = SessionStore()
        request.session["patient_id"] = str(self.patient.id)
        request.session["authenticated"] = True
        request.session.save()
        return request


class AvailableSurveysViewTest(ViewTestBase):
    def test_returns_empty_state(self):
        request = self._make_request()
        response = available_surveys(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"All caught up", response.content)

    def test_returns_survey_card(self):
        assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )
        now = timezone.now()
        SurveyInstance.objects.create(
            assignment=assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="available",
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
        )
        request = self._make_request()
        response = available_surveys(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Patient Health Questionnaire", response.content)
        self.assertIn(b"Start", response.content)

    def test_unauthenticated_returns_403(self):
        factory = RequestFactory()
        request = factory.get("/")
        from django.contrib.sessions.backends.db import SessionStore

        request.session = SessionStore()
        request.session.save()
        response = available_surveys(request)
        self.assertEqual(response.status_code, 403)


class ScoreHistoryViewTest(ViewTestBase):
    def test_returns_empty_state(self):
        request = self._make_request()
        response = score_history(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No check-ins completed yet", response.content)

    def test_returns_completed_survey(self):
        assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="daily",
            start_date=date.today(),
        )
        now = timezone.now()
        SurveyInstance.objects.create(
            assignment=assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="completed",
            due_date=date.today(),
            window_start=now - timedelta(days=1),
            window_end=now,
            completed_at=now,
            total_score=2.0,
        )
        request = self._make_request()
        response = score_history(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recent Check-ins", response.content)


class StartSurveyViewTest(ViewTestBase):
    def test_start_survey(self):
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
            status="available",
            due_date=date.today(),
            window_start=now,
            window_end=now + timedelta(days=1),
        )
        request = self._make_request(method="POST")
        response = start_survey(request, instance.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"surveyWizardConfig", response.content)
        instance.refresh_from_db()
        self.assertEqual(instance.status, "in_progress")


class SubmitAnswersViewTest(ViewTestBase):
    def test_submit_answers(self):
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
            started_at=now,
        )
        request = self._make_request(method="POST", data={"q_interest": "1"})
        response = submit_answers(request, instance.id)
        self.assertEqual(response.status_code, 204)


class CompleteSurveyViewTest(ViewTestBase):
    def test_complete_survey(self):
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
            started_at=now,
        )
        AgentConversation.objects.create(patient=self.patient, status="active")
        request = self._make_request(method="POST", data={"q_interest": "0", "q_depressed": "1"})
        response = complete_survey(request, instance.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Minimal concerns", response.content)
        instance.refresh_from_db()
        self.assertEqual(instance.status, "completed")


# =============================================================================
# Clinician-facing views (use Django test client with login)
# =============================================================================


class ClinicianViewTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(name="Clin Hospital", code="CLV")
        cls.clin_user = User.objects.create_user(
            username="dr_survey_test",
            password="testpass",  # pragma: allowlist secret
            role="clinician",
            first_name="Survey",
            last_name="Doctor",
        )
        cls.clinician = Clinician.objects.create(
            user=cls.clin_user,
            role="physician",
            is_active=True,
        )
        cls.clinician.hospitals.add(cls.hospital)

        cls.pat_user = User.objects.create_user(
            username="clin_patient",
            password="testpass",  # pragma: allowlist secret
            role="patient",
        )
        cls.patient = Patient.objects.create(
            user=cls.pat_user,
            hospital=cls.hospital,
            date_of_birth=date(1960, 1, 1),
        )
        from django.core.management import call_command

        call_command("seed_instruments", verbosity=0)
        cls.instrument = SurveyInstrument.objects.get(code="phq_2")

    def setUp(self):
        self.client.login(
            username="dr_survey_test",
            password="testpass",  # pragma: allowlist secret
        )


class ClinicianSurveysTabTest(ClinicianViewTestBase):
    def test_tab_empty(self):
        response = self.client.get(f"/patient/surveys/clinician/{self.patient.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No survey data", response.content)

    def test_tab_with_assignment(self):
        SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="weekly",
            start_date=date.today(),
        )
        response = self.client.get(f"/patient/surveys/clinician/{self.patient.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Patient Health Questionnaire", response.content)
        self.assertIn(b"Active Assignments", response.content)

    def test_tab_with_completed(self):
        assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="weekly",
            start_date=date.today(),
        )
        now = timezone.now()
        SurveyInstance.objects.create(
            assignment=assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="completed",
            due_date=date.today(),
            window_start=now - timedelta(days=1),
            window_end=now,
            completed_at=now,
            total_score=2.0,
        )
        response = self.client.get(f"/patient/surveys/clinician/{self.patient.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recent Completions", response.content)

    def test_unauthenticated_redirects(self):
        self.client.logout()
        response = self.client.get(f"/patient/surveys/clinician/{self.patient.id}/")
        self.assertNotEqual(response.status_code, 200)


class AssignSurveyViewTest(ClinicianViewTestBase):
    def test_assign_success(self):
        response = self.client.post(
            f"/patient/surveys/clinician/{self.patient.id}/assign/",
            {"instrument_code": "phq_2", "schedule_type": "weekly"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"assigned successfully", response.content)
        self.assertTrue(SurveyAssignment.objects.filter(patient=self.patient, instrument__code="phq_2").exists())

    def test_assign_invalid_instrument(self):
        response = self.client.post(
            f"/patient/surveys/clinician/{self.patient.id}/assign/",
            {"instrument_code": "nonexistent", "schedule_type": "weekly"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Failed to assign", response.content)


class DeactivateAssignmentViewTest(ClinicianViewTestBase):
    def test_deactivate(self):
        assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="weekly",
            start_date=date.today(),
        )
        response = self.client.post(f"/patient/surveys/clinician/assignment/{assignment.id}/deactivate/")
        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)


class SurveyResultsViewTest(ClinicianViewTestBase):
    def test_results_view(self):
        assignment = SurveyAssignment.objects.create(
            patient=self.patient,
            instrument=self.instrument,
            schedule_type="weekly",
            start_date=date.today(),
        )
        now = timezone.now()
        instance = SurveyInstance.objects.create(
            assignment=assignment,
            patient=self.patient,
            instrument=self.instrument,
            status="completed",
            due_date=date.today(),
            window_start=now - timedelta(days=1),
            window_end=now,
            completed_at=now,
            total_score=2.0,
            raw_scores={"interest": 1, "depressed": 1},
        )
        q1 = self.instrument.questions.get(code="interest")
        q2 = self.instrument.questions.get(code="depressed")
        SurveyAnswer.objects.create(instance=instance, question=q1, value=1, raw_value="1")
        SurveyAnswer.objects.create(instance=instance, question=q2, value=1, raw_value="1")

        response = self.client.get(f"/patient/surveys/clinician/instance/{instance.id}/results/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Patient Health Questionnaire", response.content)
