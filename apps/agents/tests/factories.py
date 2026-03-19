"""Factory Boy factories for testing."""

import uuid
from datetime import date, datetime, timedelta

import factory
from django.contrib.auth import get_user_model

from apps.accounts.models import User
from apps.patients.models import Hospital, Patient
from apps.agents.models import (
    AgentConversation,
    AgentMessage,
    ConversationState,
    Escalation,
    AgentAuditLog,
)


class HospitalFactory(factory.django.DjangoModelFactory):
    """Factory for Hospital model."""

    class Meta:
        model = Hospital

    name = factory.Sequence(lambda n: f"Test Hospital {n}")
    code = factory.Sequence(lambda n: f"HOSP{n:04d}")
    is_active = True


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for User model."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.Sequence(lambda n: f"test{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    phone_number = factory.Sequence(lambda n: f"+1555000{n:04d}")
    is_active = True


class PatientFactory(factory.django.DjangoModelFactory):
    """Factory for Patient model."""

    class Meta:
        model = Patient

    user = factory.SubFactory(UserFactory)
    hospital = factory.SubFactory(HospitalFactory)
    date_of_birth = factory.Faker("date_of_birth")
    surgery_type = "Knee Replacement"
    surgery_date = factory.LazyFunction(lambda: date.today() - timedelta(days=5))
    leaflet_code = factory.Sequence(lambda n: f"PAT{n:04d}")
    status = "green"


class AgentConversationFactory(factory.django.DjangoModelFactory):
    """Factory for AgentConversation model."""

    class Meta:
        model = AgentConversation

    patient = factory.SubFactory(PatientFactory)
    agent_type = "supervisor"
    status = "active"
    context = factory.LazyFunction(dict)
    tool_invocations = factory.LazyFunction(list)
    escalation_reason = ""


class AgentMessageFactory(factory.django.DjangoModelFactory):
    """Factory for AgentMessage model."""

    class Meta:
        model = AgentMessage

    conversation = factory.SubFactory(AgentConversationFactory)
    role = "user"
    content = factory.Faker("sentence")
    agent_type = ""
    routing_decision = ""
    confidence_score = None
    escalation_triggered = False
    escalation_reason = ""
    metadata = factory.LazyFunction(dict)


class ConversationStateFactory(factory.django.DjangoModelFactory):
    """Factory for ConversationState model."""

    class Meta:
        model = ConversationState

    conversation = factory.SubFactory(AgentConversationFactory)
    patient_summary = factory.Faker("sentence")
    recent_symptoms = factory.LazyFunction(list)
    medications = factory.LazyFunction(list)
    recovery_phase = "early"


class EscalationFactory(factory.django.DjangoModelFactory):
    """Factory for Escalation model."""

    class Meta:
        model = Escalation

    patient = factory.SubFactory(PatientFactory)
    conversation = factory.SubFactory(AgentConversationFactory)
    reason = factory.Faker("sentence")
    severity = "urgent"
    status = "pending"
    conversation_summary = factory.Faker("text", max_nb_chars=200)
    patient_context = factory.LazyFunction(dict)


class AgentAuditLogFactory(factory.django.DjangoModelFactory):
    """Factory for AgentAuditLog model."""

    class Meta:
        model = AgentAuditLog

    patient = factory.SubFactory(PatientFactory)
    action = "message_processed"
    agent_type = "care_coordinator"
    details = factory.LazyFunction(dict)
    ip_address = "127.0.0.1"
    user_agent = "Mozilla/5.0 (Test)"
