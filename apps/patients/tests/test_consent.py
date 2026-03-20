"""Tests for patient consent management."""

import pytest

from apps.agents.tests.factories import PatientFactory
from apps.patients.models import ConsentRecord


@pytest.mark.django_db
class TestConsentRecord:
    def test_create_consent_grant(self):
        patient = PatientFactory()
        user = patient.user
        consent = ConsentRecord.objects.create(
            patient=patient,
            consent_type="ai_interaction",
            granted=True,
            granted_by=user,
            ip_address="127.0.0.1",
        )
        assert consent.granted is True
        assert consent.granted_at is not None
        assert consent.revoked_at is None

    def test_consent_str_granted(self):
        patient = PatientFactory()
        consent = ConsentRecord.objects.create(
            patient=patient,
            consent_type="communication_sms",
            granted=True,
        )
        assert "granted" in str(consent)
        assert "communication_sms" in str(consent)

    def test_consent_str_revoked(self):
        patient = PatientFactory()
        consent = ConsentRecord.objects.create(
            patient=patient,
            consent_type="communication_sms",
            granted=False,
        )
        assert "revoked" in str(consent)

    def test_all_consent_types_defined(self):
        types = [c[0] for c in ConsentRecord.CONSENT_TYPE_CHOICES]
        assert "data_sharing_caregiver" in types
        assert "data_sharing_research" in types
        assert "communication_sms" in types
        assert "communication_email" in types
        assert "ai_interaction" in types


@pytest.mark.django_db
class TestHasConsent:
    def test_has_consent_when_granted(self):
        patient = PatientFactory()
        ConsentRecord.objects.create(
            patient=patient,
            consent_type="ai_interaction",
            granted=True,
        )
        assert ConsentRecord.has_consent(patient, "ai_interaction") is True

    def test_no_consent_when_not_granted(self):
        patient = PatientFactory()
        assert ConsentRecord.has_consent(patient, "ai_interaction") is False

    def test_consent_revoked_after_grant(self):
        patient = PatientFactory()
        ConsentRecord.objects.create(
            patient=patient,
            consent_type="communication_sms",
            granted=True,
        )
        ConsentRecord.objects.create(
            patient=patient,
            consent_type="communication_sms",
            granted=False,
        )
        assert ConsentRecord.has_consent(patient, "communication_sms") is False

    def test_consent_regranted_after_revocation(self):
        patient = PatientFactory()
        ConsentRecord.objects.create(
            patient=patient,
            consent_type="data_sharing_caregiver",
            granted=True,
        )
        ConsentRecord.objects.create(
            patient=patient,
            consent_type="data_sharing_caregiver",
            granted=False,
        )
        ConsentRecord.objects.create(
            patient=patient,
            consent_type="data_sharing_caregiver",
            granted=True,
        )
        assert ConsentRecord.has_consent(patient, "data_sharing_caregiver") is True

    def test_consent_types_independent(self):
        patient = PatientFactory()
        ConsentRecord.objects.create(
            patient=patient,
            consent_type="ai_interaction",
            granted=True,
        )
        assert ConsentRecord.has_consent(patient, "ai_interaction") is True
        assert ConsentRecord.has_consent(patient, "communication_sms") is False

    def test_consent_per_patient(self):
        patient1 = PatientFactory()
        patient2 = PatientFactory()
        ConsentRecord.objects.create(
            patient=patient1,
            consent_type="ai_interaction",
            granted=True,
        )
        assert ConsentRecord.has_consent(patient1, "ai_interaction") is True
        assert ConsentRecord.has_consent(patient2, "ai_interaction") is False
