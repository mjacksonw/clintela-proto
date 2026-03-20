"""Tests for knowledge app models."""

import hashlib

import pytest
from django.db import IntegrityError

from apps.agents.models import MessageCitation
from apps.agents.tests.factories import AgentMessageFactory
from apps.knowledge.models import KnowledgeSource

from .factories import (
    KnowledgeDocumentFactory,
    KnowledgeGapFactory,
    KnowledgeSourceFactory,
)


@pytest.mark.django_db
class TestKnowledgeSource:
    def test_create_global_source(self):
        source = KnowledgeSourceFactory(hospital=None)
        assert source.hospital is None
        assert source.is_active is True
        assert str(source) == f"{source.name} (global)"

    def test_create_tenant_scoped_source(self):
        source = KnowledgeSourceFactory(tenant_scoped=True)
        assert source.hospital is not None
        assert source.source_type == "hospital_protocol"
        assert source.hospital.code in str(source)

    def test_source_types(self):
        for source_type, _ in KnowledgeSource.SOURCE_TYPES:
            source = KnowledgeSourceFactory(source_type=source_type)
            assert source.source_type == source_type

    def test_provenance_tracking(self):
        from apps.agents.tests.factories import UserFactory

        user = UserFactory()
        source = KnowledgeSourceFactory(created_by=user, updated_by=user)
        assert source.created_by == user
        assert source.updated_by == user


@pytest.mark.django_db
class TestKnowledgeDocument:
    def test_create_document(self):
        doc = KnowledgeDocumentFactory()
        assert doc.source is not None
        assert len(doc.embedding) == 768
        assert doc.is_active is True

    def test_content_hash_auto_generated(self):
        doc = KnowledgeDocumentFactory(content="test content", content_hash="")
        doc.save()
        expected_hash = hashlib.sha256(b"test content").hexdigest()
        assert doc.content_hash == expected_hash

    def test_content_hash_dedup_constraint(self):
        source = KnowledgeSourceFactory()
        content_hash = hashlib.sha256(b"duplicate content").hexdigest()
        KnowledgeDocumentFactory(source=source, content_hash=content_hash)
        with pytest.raises(IntegrityError):
            KnowledgeDocumentFactory(source=source, content_hash=content_hash)

    def test_different_sources_same_hash_allowed(self):
        content_hash = hashlib.sha256(b"shared content").hexdigest()
        source1 = KnowledgeSourceFactory()
        source2 = KnowledgeSourceFactory()
        doc1 = KnowledgeDocumentFactory(source=source1, content_hash=content_hash)
        doc2 = KnowledgeDocumentFactory(source=source2, content_hash=content_hash)
        assert doc1.pk != doc2.pk

    def test_chunk_metadata(self):
        doc = KnowledgeDocumentFactory(
            chunk_metadata={
                "section_path": "CABG > Post-Op > Day 1-3",
                "page_numbers": [12, 13],
                "recommendation_class": "I",
                "level_of_evidence": "A",
            }
        )
        assert doc.chunk_metadata["section_path"] == "CABG > Post-Op > Day 1-3"


@pytest.mark.django_db
class TestKnowledgeGap:
    def test_create_gap(self):
        gap = KnowledgeGapFactory(query="Can I take ibuprofen with warfarin?")
        assert gap.max_similarity == 0.0
        assert "ibuprofen" in str(gap)

    def test_gap_with_hospital(self):
        from apps.agents.tests.factories import HospitalFactory

        hospital = HospitalFactory()
        gap = KnowledgeGapFactory(hospital=hospital)
        assert gap.hospital == hospital

    def test_gap_without_patient(self):
        gap = KnowledgeGapFactory(patient=None)
        assert gap.patient is None


@pytest.mark.django_db
class TestMessageCitation:
    def test_create_citation(self):
        msg = AgentMessageFactory(role="assistant", agent_type="care_coordinator")
        doc = KnowledgeDocumentFactory()
        citation = MessageCitation.objects.create(
            agent_message=msg,
            knowledge_doc=doc,
            similarity_score=0.89,
        )
        assert citation.similarity_score == 0.89
        assert citation.agent_message == msg
        assert citation.knowledge_doc == doc

    def test_citation_unique_constraint(self):
        msg = AgentMessageFactory(role="assistant")
        doc = KnowledgeDocumentFactory()
        MessageCitation.objects.create(agent_message=msg, knowledge_doc=doc, similarity_score=0.9)
        with pytest.raises(IntegrityError):
            MessageCitation.objects.create(agent_message=msg, knowledge_doc=doc, similarity_score=0.8)

    def test_m2m_through_cited_documents(self):
        msg = AgentMessageFactory(role="assistant")
        doc1 = KnowledgeDocumentFactory()
        doc2 = KnowledgeDocumentFactory()
        MessageCitation.objects.create(agent_message=msg, knowledge_doc=doc1, similarity_score=0.9)
        MessageCitation.objects.create(agent_message=msg, knowledge_doc=doc2, similarity_score=0.8)
        assert msg.cited_documents.count() == 2
