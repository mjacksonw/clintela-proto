"""Tests for patient lifecycle state machine."""

import pytest

from apps.agents.tests.factories import PatientFactory
from apps.patients.models import InvalidLifecycleTransitionError, Patient, PatientStatusTransition


@pytest.mark.django_db
class TestLifecycleStatus:
    def test_default_lifecycle_is_pre_surgery(self):
        patient = PatientFactory()
        assert patient.lifecycle_status == "pre_surgery"

    def test_all_lifecycle_choices_defined(self):
        statuses = [c[0] for c in Patient.LIFECYCLE_CHOICES]
        assert "pre_surgery" in statuses
        assert "admitted" in statuses
        assert "in_surgery" in statuses
        assert "post_op" in statuses
        assert "discharged" in statuses
        assert "recovering" in statuses
        assert "recovered" in statuses
        assert "readmitted" in statuses

    def test_every_status_has_transition_entry(self):
        """Every lifecycle status should appear as a key in LIFECYCLE_TRANSITIONS."""
        for status, _ in Patient.LIFECYCLE_CHOICES:
            assert status in Patient.LIFECYCLE_TRANSITIONS


@pytest.mark.django_db
class TestLifecycleTransitions:
    def test_valid_transition_pre_surgery_to_admitted(self):
        patient = PatientFactory(lifecycle_status="pre_surgery")
        transition = patient.transition_lifecycle("admitted", triggered_by="clinician:jane")

        patient.refresh_from_db()
        assert patient.lifecycle_status == "admitted"
        assert transition.from_status == "pre_surgery"
        assert transition.to_status == "admitted"
        assert transition.triggered_by == "clinician:jane"

    def test_full_happy_path(self):
        """Walk the full lifecycle: pre_surgery → ... → recovered."""
        patient = PatientFactory(lifecycle_status="pre_surgery")
        path = ["admitted", "in_surgery", "post_op", "discharged", "recovering", "recovered"]

        for status in path:
            patient.transition_lifecycle(status, triggered_by="system")

        patient.refresh_from_db()
        assert patient.lifecycle_status == "recovered"
        assert PatientStatusTransition.objects.filter(patient=patient).count() == len(path)

    def test_readmission_path(self):
        """Patient can be readmitted from recovering."""
        patient = PatientFactory(lifecycle_status="recovering")
        patient.transition_lifecycle("readmitted", triggered_by="system", reason="Complication")

        patient.refresh_from_db()
        assert patient.lifecycle_status == "readmitted"

        # Readmitted can go back to admitted
        patient.transition_lifecycle("admitted", triggered_by="clinician:john")
        patient.refresh_from_db()
        assert patient.lifecycle_status == "admitted"

    def test_invalid_transition_raises(self):
        patient = PatientFactory(lifecycle_status="pre_surgery")
        with pytest.raises(InvalidLifecycleTransitionError, match="Cannot transition"):
            patient.transition_lifecycle("discharged")

    def test_cannot_skip_statuses(self):
        patient = PatientFactory(lifecycle_status="admitted")
        with pytest.raises(InvalidLifecycleTransitionError):
            patient.transition_lifecycle("discharged")

    def test_recovered_is_terminal(self):
        patient = PatientFactory(lifecycle_status="recovered")
        with pytest.raises(InvalidLifecycleTransitionError):
            patient.transition_lifecycle("readmitted")

    def test_transition_creates_audit_record(self):
        patient = PatientFactory(lifecycle_status="pre_surgery")
        transition = patient.transition_lifecycle(
            "admitted",
            triggered_by="system",
            reason="Scheduled admission",
        )
        assert isinstance(transition, PatientStatusTransition)
        assert transition.patient == patient
        assert transition.reason == "Scheduled admission"
        assert transition.created_at is not None

    def test_transition_does_not_change_triage_status(self):
        """Lifecycle transitions should not affect the triage status."""
        patient = PatientFactory(lifecycle_status="pre_surgery", status="yellow")
        patient.transition_lifecycle("admitted")
        patient.refresh_from_db()
        assert patient.status == "yellow"
        assert patient.lifecycle_status == "admitted"

    def test_transition_history_ordered_by_created(self):
        patient = PatientFactory(lifecycle_status="pre_surgery")
        patient.transition_lifecycle("admitted")
        patient.transition_lifecycle("in_surgery")

        transitions = list(patient.lifecycle_transitions.all())
        assert len(transitions) == 2
        # Ordered by -created_at, so newest first
        assert transitions[0].to_status == "in_surgery"
        assert transitions[1].to_status == "admitted"


@pytest.mark.django_db
class TestEscalationExtensions:
    def test_escalation_type_default(self):
        from apps.agents.tests.factories import EscalationFactory

        escalation = EscalationFactory()
        assert escalation.escalation_type == "clinical"

    def test_escalation_type_choices(self):
        from apps.agents.models import Escalation

        types = [c[0] for c in Escalation.ESCALATION_TYPE_CHOICES]
        assert "clinical" in types
        assert "specialist_referral" in types
        assert "social_work" in types
        assert "pharmacy_consult" in types

    def test_escalation_priority_score(self):
        from apps.agents.tests.factories import EscalationFactory

        escalation = EscalationFactory()
        assert escalation.priority_score == 0.0

    def test_escalation_response_deadline_nullable(self):
        from apps.agents.tests.factories import EscalationFactory

        escalation = EscalationFactory()
        assert escalation.response_deadline is None
