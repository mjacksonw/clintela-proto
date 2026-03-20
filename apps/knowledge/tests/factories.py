"""Factory Boy factories for knowledge app testing."""

import uuid

import factory

from apps.agents.tests.factories import AgentMessageFactory, HospitalFactory, PatientFactory
from apps.knowledge.models import KnowledgeDocument, KnowledgeGap, KnowledgeSource


class KnowledgeSourceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = KnowledgeSource

    name = factory.Sequence(lambda n: f"Test Guideline {n}")
    source_type = "acc_guideline"
    hospital = None  # Global by default
    version = "2024.1"
    is_active = True
    metadata = factory.LazyFunction(dict)

    class Params:
        tenant_scoped = factory.Trait(
            hospital=factory.SubFactory(HospitalFactory),
            source_type="hospital_protocol",
        )


class KnowledgeDocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = KnowledgeDocument

    source = factory.SubFactory(KnowledgeSourceFactory)
    title = factory.Sequence(lambda n: f"Test Chunk {n}")
    content = factory.Faker("paragraph", nb_sentences=5)
    chunk_index = factory.Sequence(lambda n: n)
    chunk_metadata = factory.LazyFunction(lambda: {"section_path": "Test > Section"})
    embedding = factory.LazyFunction(lambda: [0.0] * 768)
    token_count = 256
    content_hash = factory.LazyFunction(lambda: uuid.uuid4().hex + uuid.uuid4().hex[:32])
    is_active = True


class KnowledgeGapFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = KnowledgeGap

    query = factory.Faker("sentence")
    hospital = None
    max_similarity = 0.0
    agent_type = "care_coordinator"
    patient = factory.SubFactory(PatientFactory)


# Re-export for convenience
__all__ = [
    "KnowledgeSourceFactory",
    "KnowledgeDocumentFactory",
    "KnowledgeGapFactory",
    "AgentMessageFactory",
    "HospitalFactory",
    "PatientFactory",
]
