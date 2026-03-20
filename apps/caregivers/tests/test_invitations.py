"""Tests for caregiver invitation flow."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.agents.tests.factories import PatientFactory, UserFactory
from apps.caregivers.models import (
    Caregiver,
    CaregiverInvitation,
    CaregiverRelationship,
    InvalidInvitationError,
    LeafletCodeMismatchError,
)


@pytest.mark.django_db
class TestCaregiverInvitationModel:
    def test_create_invitation(self):
        patient = PatientFactory()
        invite = CaregiverInvitation.objects.create(
            patient=patient,
            name="Sarah Johnson",
            email="sarah@example.com",
            relationship="spouse",
        )
        assert invite.status == "pending"
        assert invite.token
        assert len(invite.token) > 20
        assert invite.expires_at > timezone.now()
        assert invite.is_acceptable is True

    def test_unique_tokens(self):
        patient = PatientFactory()
        inv1 = CaregiverInvitation.objects.create(patient=patient, name="A", relationship="spouse")
        inv2 = CaregiverInvitation.objects.create(patient=patient, name="B", relationship="child")
        assert inv1.token != inv2.token

    def test_invitation_str(self):
        patient = PatientFactory()
        invite = CaregiverInvitation.objects.create(patient=patient, name="Sarah", relationship="spouse")
        assert "Sarah" in str(invite)
        assert "pending" in str(invite)

    def test_is_expired_after_expiry(self):
        patient = PatientFactory()
        invite = CaregiverInvitation.objects.create(
            patient=patient,
            name="Test",
            relationship="friend",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert invite.is_expired is True
        assert invite.is_acceptable is False

    def test_is_not_expired_before_expiry(self):
        patient = PatientFactory()
        invite = CaregiverInvitation.objects.create(
            patient=patient,
            name="Test",
            relationship="friend",
            expires_at=timezone.now() + timedelta(days=3),
        )
        assert invite.is_expired is False
        assert invite.is_acceptable is True


@pytest.mark.django_db
class TestAcceptInvitation:
    def test_accept_valid_invitation(self):
        patient = PatientFactory(leaflet_code="LEAF001")
        invite = CaregiverInvitation.objects.create(
            patient=patient,
            name="Sarah",
            email="sarah@example.com",
            relationship="spouse",
        )
        caregiver_user = UserFactory(role="caregiver")

        rel = invite.accept(caregiver_user, "LEAF001")

        invite.refresh_from_db()
        assert invite.status == "accepted"
        assert invite.accepted_by == caregiver_user
        assert invite.accepted_at is not None
        assert rel.patient == patient
        assert rel.relationship == "spouse"
        assert rel.is_active is True

    def test_accept_creates_caregiver_profile(self):
        patient = PatientFactory(leaflet_code="LEAF002")
        invite = CaregiverInvitation.objects.create(patient=patient, name="Tom", relationship="child")
        user = UserFactory(role="caregiver")

        invite.accept(user, "LEAF002")

        assert Caregiver.objects.filter(user=user).exists()
        caregiver = Caregiver.objects.get(user=user)
        assert caregiver.is_verified is True

    def test_accept_wrong_leaflet_code_raises(self):
        patient = PatientFactory(leaflet_code="LEAF003")
        invite = CaregiverInvitation.objects.create(patient=patient, name="Test", relationship="friend")
        user = UserFactory(role="caregiver")

        with pytest.raises(LeafletCodeMismatchError, match="Invalid"):
            invite.accept(user, "WRONG_CODE")

        invite.refresh_from_db()
        assert invite.status == "pending"

    def test_accept_expired_invitation_raises(self):
        patient = PatientFactory(leaflet_code="LEAF004")
        invite = CaregiverInvitation.objects.create(
            patient=patient,
            name="Test",
            relationship="friend",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        user = UserFactory(role="caregiver")

        with pytest.raises(InvalidInvitationError):
            invite.accept(user, "LEAF004")

        invite.refresh_from_db()
        assert invite.status == "expired"

    def test_cannot_accept_already_accepted(self):
        patient = PatientFactory(leaflet_code="LEAF005")
        invite = CaregiverInvitation.objects.create(patient=patient, name="Test", relationship="spouse")
        user = UserFactory(role="caregiver")
        invite.accept(user, "LEAF005")

        user2 = UserFactory(role="caregiver")
        with pytest.raises(InvalidInvitationError):
            invite.accept(user2, "LEAF005")

    def test_accept_reactivates_existing_relationship(self):
        """If caregiver already had a revoked relationship, reactivate it."""
        patient = PatientFactory(leaflet_code="LEAF006")
        user = UserFactory(role="caregiver")
        caregiver = Caregiver.objects.create(user=user, is_verified=True)
        CaregiverRelationship.objects.create(
            caregiver=caregiver,
            patient=patient,
            relationship="spouse",
            is_active=False,
        )

        invite = CaregiverInvitation.objects.create(patient=patient, name="Test", relationship="parent")
        rel = invite.accept(user, "LEAF006")

        assert rel.is_active is True
        assert rel.relationship == "parent"
        assert CaregiverRelationship.objects.filter(caregiver=caregiver, patient=patient).count() == 1


@pytest.mark.django_db
class TestRevokeInvitation:
    def test_revoke_pending_invitation(self):
        patient = PatientFactory()
        invite = CaregiverInvitation.objects.create(patient=patient, name="Test", relationship="friend")
        invite.revoke()

        invite.refresh_from_db()
        assert invite.status == "revoked"
        assert invite.revoked_at is not None

    def test_revoke_accepted_invitation(self):
        patient = PatientFactory(leaflet_code="LEAF007")
        invite = CaregiverInvitation.objects.create(patient=patient, name="Test", relationship="friend")
        user = UserFactory(role="caregiver")
        invite.accept(user, "LEAF007")

        invite.revoke()
        invite.refresh_from_db()
        assert invite.status == "revoked"

    def test_cannot_revoke_expired(self):
        patient = PatientFactory()
        invite = CaregiverInvitation.objects.create(
            patient=patient,
            name="Test",
            relationship="friend",
            status="expired",
        )
        with pytest.raises(InvalidInvitationError):
            invite.revoke()

    def test_cannot_revoke_already_revoked(self):
        patient = PatientFactory()
        invite = CaregiverInvitation.objects.create(
            patient=patient,
            name="Test",
            relationship="friend",
            status="revoked",
        )
        with pytest.raises(InvalidInvitationError):
            invite.revoke()
