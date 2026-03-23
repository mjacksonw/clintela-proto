"""Coverage tests for agents admin configuration."""

from datetime import date

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from apps.accounts.models import User
from apps.agents.admin import AgentConversationAdmin, AgentMessageAdmin, EscalationAdmin
from apps.agents.models import AgentConversation, AgentMessage, Escalation
from apps.patients.models import Hospital, Patient


@pytest.fixture
def site():
    return AdminSite()


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def patient(db):
    hospital = Hospital.objects.create(name="Admin Test Hospital")
    user = User.objects.create_user(
        username="admin_test_pat",
        password="test",  # pragma: allowlist secret
        first_name="Admin",
        last_name="Patient",
    )
    return Patient.objects.create(user=user, hospital=hospital, date_of_birth=date(1970, 1, 1))


@pytest.mark.django_db
class TestAgentConversationAdmin:
    def test_get_patient_name(self, site, patient):
        conv = AgentConversation.objects.create(patient=patient)
        admin = AgentConversationAdmin(AgentConversation, site)
        assert admin.get_patient_name(conv) == "Admin Patient"

    def test_permissions(self, site, rf):
        admin = AgentConversationAdmin(AgentConversation, site)
        request = rf.get("/")
        assert admin.has_add_permission(request) is False
        assert admin.has_change_permission(request) is False
        assert admin.has_delete_permission(request) is False


@pytest.mark.django_db
class TestAgentMessageAdmin:
    def test_permissions(self, site, rf):
        admin = AgentMessageAdmin(AgentMessage, site)
        request = rf.get("/")
        assert admin.has_add_permission(request) is False
        assert admin.has_change_permission(request) is False
        assert admin.has_delete_permission(request) is False


@pytest.mark.django_db
class TestEscalationAdmin:
    def test_get_patient_name(self, site, patient):
        esc = Escalation.objects.create(patient=patient, severity="routine", status="pending", reason="Test")
        admin = EscalationAdmin(Escalation, site)
        assert admin.get_patient_name(esc) == "Admin Patient"

    def test_permissions(self, site, rf):
        admin = EscalationAdmin(Escalation, site)
        request = rf.get("/")
        assert admin.has_add_permission(request) is False
        assert admin.has_change_permission(request) is False
        assert admin.has_delete_permission(request) is False
