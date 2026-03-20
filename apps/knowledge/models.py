"""Knowledge app - Clinical knowledge RAG models.

Data model for clinical knowledge retrieval:

    KnowledgeSource (ACC guideline, hospital protocol, etc.)
        │
        ├── KnowledgeDocument (chunked content with embeddings)
        │       │
        │       └── [vector index for semantic search]
        │       └── [tsvector index for full-text search]
        │
        └── hospital FK (NULL = global, non-null = tenant-scoped)

    KnowledgeGap (tracks unanswered patient questions)

Multi-tenancy: retrieval queries filter by
    hospital IS NULL (global ACC) OR hospital = patient.hospital
"""

import hashlib
import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from pgvector.django import HnswIndex, VectorField


class KnowledgeSource(models.Model):
    """A source of clinical knowledge (guideline, protocol, research paper)."""

    SOURCE_TYPES = [
        ("acc_guideline", "ACC Guideline"),
        ("clinical_research", "Clinical Research"),
        ("hospital_protocol", "Hospital Protocol"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES)
    url = models.URLField(blank=True)
    hospital = models.ForeignKey(
        "patients.Hospital",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="knowledge_sources",
        help_text="NULL = global (e.g. ACC guidelines), non-null = tenant-scoped",
    )
    version = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    last_ingested_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    # Provenance tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_knowledge_sources",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_knowledge_sources",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "knowledge_source"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["hospital", "is_active"], name="idx_ks_hospital_active"),
            models.Index(fields=["source_type"], name="idx_ks_source_type"),
        ]

    def __str__(self):
        scope = self.hospital.code if self.hospital else "global"
        return f"{self.name} ({scope})"


class KnowledgeDocument(models.Model):
    """A chunk of clinical knowledge with embedding for vector search.

    Each document is a semantic chunk from a KnowledgeSource, sized at
    256-512 tokens with 50-token overlap. Embeddings are 768-dimensional
    vectors from nomic-embed-text via Ollama.

    Hybrid search combines:
        0.7 * cosine_similarity(embedding) + 0.3 * ts_rank(search_vector)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        KnowledgeSource,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    title = models.CharField(max_length=500)
    content = models.TextField()
    chunk_index = models.IntegerField()
    chunk_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Section path, page numbers, recommendation class/level",
    )

    # Vector embedding for semantic search
    embedding = VectorField(dimensions=768)

    # Full-text search vector for hybrid search
    search_vector = SearchVectorField(null=True)

    token_count = models.IntegerField(default=0)
    content_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of content for deduplication",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "knowledge_document"
        ordering = ["source", "chunk_index"]
        indexes = [
            HnswIndex(
                name="idx_kd_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
            GinIndex(
                name="idx_kd_search_vector",
                fields=["search_vector"],
            ),
            models.Index(
                fields=["source", "is_active"],
                name="idx_kd_source_active",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "content_hash"],
                name="uq_kd_source_content_hash",
            ),
        ]

    def __str__(self):
        return f"{self.source.name} — {self.title} (chunk {self.chunk_index})"

    def save(self, *args, **kwargs):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()
        super().save(*args, **kwargs)


class KnowledgeGap(models.Model):
    """Tracks patient questions that couldn't be answered by the knowledge base.

    Used to surface coverage gaps to admins so they can prioritize
    new content ingestion. Grouped by similarity for the admin dashboard.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.TextField(help_text="The patient's question that had no good match")
    hospital = models.ForeignKey(
        "patients.Hospital",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_gaps",
    )
    max_similarity = models.FloatField(
        default=0.0,
        help_text="Best similarity score from retrieval (0 if no results)",
    )
    agent_type = models.CharField(max_length=30, blank=True)
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_gaps",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "knowledge_gap"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["hospital", "created_at"],
                name="idx_kg_hospital_created",
            ),
        ]

    def __str__(self):
        return f"Gap: {self.query[:80]}..."
