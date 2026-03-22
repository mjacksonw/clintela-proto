"""Migrate embedding dimensions from 768 (nomic-embed-text) to 2000 (Qwen3-Embedding-4B).

Qwen3-Embedding-4B produces 2560-dimensional vectors natively, but pgvector's
HNSW index has a 2000-dimension limit (8KB page size constraint). Using 2000
via Matryoshka truncation retains excellent retrieval quality.

This migration:
1. Drops the existing HNSW index (requires matching dimensions)
2. Clears existing embeddings (incompatible dimensions)
3. Alters the vector column from 768 to 2000 dimensions
4. Recreates the HNSW index with the new dimensions

Existing embeddings must be re-generated after migration.
"""

from django.db import migrations

import pgvector.django.vector


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0002_phase4_admin_dashboard"),
    ]

    operations = [
        # 1. Drop the HNSW index (it's tied to 768 dimensions)
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS idx_kd_embedding_hnsw;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 2. Clear existing embeddings (they're 768-dim, incompatible with 2000)
        migrations.RunSQL(
            sql="UPDATE knowledge_document SET embedding = NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 3. Alter the vector column to 2000 dimensions
        migrations.AlterField(
            model_name="knowledgedocument",
            name="embedding",
            field=pgvector.django.vector.VectorField(dimensions=2000),
        ),
        # 4. Recreate HNSW index with new dimensions
        migrations.RunSQL(
            sql="""
                CREATE INDEX idx_kd_embedding_hnsw
                ON knowledge_document
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="DROP INDEX IF EXISTS idx_kd_embedding_hnsw;",
        ),
    ]
