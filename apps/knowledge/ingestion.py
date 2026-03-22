"""Ingestion pipeline: parse → chunk → sanitize → embed → store.

Pipeline flow:
    Document file → Parser → ParsedSections → Chunker → Chunks
        → Sanitizer → Clean chunks → EmbeddingClient.embed_batch()
        → KnowledgeDocument.objects.bulk_create()

Deduplication via content_hash (SHA-256) prevents re-ingesting unchanged content.
"""

import hashlib
import logging
from dataclasses import dataclass

from django.contrib.postgres.search import SearchVector
from django.utils import timezone

from .embeddings import get_embedding_client
from .models import KnowledgeDocument, KnowledgeSource
from .parsers import ParsedSection, get_parser
from .sanitizer import sanitize_content

logger = logging.getLogger(__name__)

# Chunk size tuned for Qwen3-Embedding-4B (40K token context window).
# Clinical text with abbreviations (ACC/AHA/SCAI) tokenizes to ~2.5 chars/token.
# 512-token target captures a full ACC/AHA recommendation with its evidence level.
TARGET_CHUNK_TOKENS = 512
MAX_CHUNK_TOKENS = 768
OVERLAP_TOKENS = 64
CHARS_PER_TOKEN = 2.5
# Max characters = 768 * 2.5 = 1920 chars
MAX_CHUNK_CHARS = int(MAX_CHUNK_TOKENS * CHARS_PER_TOKEN)
# Qwen3-Embedding-4B's 40K context window allows safe batching
EMBEDDING_BATCH_SIZE = 16


@dataclass
class Chunk:
    """A text chunk ready for embedding."""

    title: str
    content: str
    chunk_index: int
    section_path: str
    metadata: dict
    content_hash: str
    token_count: int


class IngestionPipeline:
    """Pipeline for ingesting documents into the knowledge base."""

    def __init__(self, source: KnowledgeSource):
        self.source = source
        self.stats = {
            "sections_parsed": 0,
            "chunks_created": 0,
            "chunks_deduplicated": 0,
            "sanitization_events": 0,
            "errors": 0,
        }

    def ingest_file(self, file_path: str, update_source: bool = True) -> dict:
        """Ingest a document file into the knowledge base.

        Args:
            file_path: Path to the document file.
            update_source: Whether to update source.last_ingested_at.

        Returns:
            Dict of ingestion statistics.
        """
        parser = get_parser(file_path)

        # PDF parser uses parse_file, others use parse on text content
        if hasattr(parser, "parse_file"):
            sections = parser.parse_file(file_path, self.source.name)
        else:
            from pathlib import Path

            text = Path(file_path).read_text(encoding="utf-8")
            sections = parser.parse(text, self.source.name)

        self.stats["sections_parsed"] = len(sections)

        if not sections:
            logger.warning("No sections parsed from %s", file_path)
            return self.stats

        # Chunk sections
        chunks = self._chunk_sections(sections)

        # Sanitize
        chunks = self._sanitize_chunks(chunks)

        # Deduplicate against existing content
        chunks = self._deduplicate(chunks)

        if not chunks:
            logger.info("All chunks already exist (deduplicated): %s", file_path)
            return self.stats

        # Embed and store
        self._embed_and_store(chunks)

        # Update search vectors
        self._update_search_vectors()

        if update_source:
            self.source.last_ingested_at = timezone.now()
            self.source.save(update_fields=["last_ingested_at", "updated_at"])

        logger.info(
            "Ingestion complete for %s: %d chunks created, %d deduplicated",
            self.source.name,
            self.stats["chunks_created"],
            self.stats["chunks_deduplicated"],
        )
        return self.stats

    def ingest_text(self, text: str, title: str = "", update_source: bool = True) -> dict:
        """Ingest raw text content directly.

        Args:
            text: Raw text content.
            title: Title for the content.
            update_source: Whether to update source.last_ingested_at.

        Returns:
            Dict of ingestion statistics.
        """
        from .parsers import TextParser

        parser = TextParser()
        sections = parser.parse(text, title or self.source.name)
        self.stats["sections_parsed"] = len(sections)

        if not sections:
            return self.stats

        chunks = self._chunk_sections(sections)
        chunks = self._sanitize_chunks(chunks)
        chunks = self._deduplicate(chunks)

        if not chunks:
            return self.stats

        self._embed_and_store(chunks)
        self._update_search_vectors()

        if update_source:
            self.source.last_ingested_at = timezone.now()
            self.source.save(update_fields=["last_ingested_at", "updated_at"])

        return self.stats

    def _chunk_sections(self, sections: list[ParsedSection]) -> list[Chunk]:
        """Split sections into chunks of TARGET_CHUNK_TOKENS size."""
        chunks = []
        chunk_index = 0

        for section in sections:
            section_chunks = self._split_text(
                text=section.content,
                title=section.title,
                section_path=section.section_path,
                page_numbers=section.page_numbers,
                metadata=section.metadata,
                start_index=chunk_index,
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)

        return chunks

    def _split_text(
        self,
        text: str,
        title: str,
        section_path: str,
        page_numbers: list[int],
        metadata: dict,
        start_index: int,
    ) -> list[Chunk]:
        """Split text into chunks with overlap.

        Uses paragraph boundaries when possible, falls back to hard character
        truncation for text without clear paragraph breaks (common in PDFs).
        """
        if len(text) <= MAX_CHUNK_CHARS:
            return [self._make_chunk(text, title, section_path, page_numbers, metadata, start_index)]

        paragraphs = self._split_into_paragraphs(text)
        return self._process_paragraphs(paragraphs, title, section_path, page_numbers, metadata, start_index)

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """Split text on paragraph boundaries, falling back to single newlines."""
        paragraphs = text.split("\n\n")
        if len(paragraphs) == 1:
            paragraphs = text.split("\n")
        return [p.strip() for p in paragraphs if p.strip()]

    def _process_paragraphs(
        self,
        paragraphs: list[str],
        title: str,
        section_path: str,
        page_numbers: list[int],
        metadata: dict,
        start_index: int,
    ) -> list[Chunk]:
        """Process paragraphs into chunks with overlap."""
        target_chars = int(TARGET_CHUNK_TOKENS * CHARS_PER_TOKEN)
        overlap_chars = int(OVERLAP_TOKENS * CHARS_PER_TOKEN)

        chunks: list[Chunk] = []
        current_text = ""
        idx = start_index

        for para in paragraphs:
            # Truncate oversized paragraphs first
            truncated, idx = self._truncate_long_paragraph(
                para, title, section_path, page_numbers, metadata, idx, chunks
            )
            para = truncated

            if not para:
                continue

            if len(current_text) + len(para) + 2 > target_chars and current_text:
                chunks.append(self._make_chunk(current_text.strip(), title, section_path, page_numbers, metadata, idx))
                idx += 1
                current_text = self._compute_overlap(current_text, para, overlap_chars)
            else:
                current_text = f"{current_text}\n\n{para}" if current_text else para

        if current_text.strip():
            chunks.append(self._make_chunk(current_text.strip(), title, section_path, page_numbers, metadata, idx))

        return chunks

    def _truncate_long_paragraph(
        self,
        para: str,
        title: str,
        section_path: str,
        page_numbers: list[int],
        metadata: dict,
        idx: int,
        chunks: list[Chunk],
    ) -> tuple[str, int]:
        """Split oversized paragraph into chunks, return remaining text and updated index."""
        while len(para) > MAX_CHUNK_CHARS:
            split_point = para.rfind(" ", 0, MAX_CHUNK_CHARS)
            if split_point == -1:
                split_point = MAX_CHUNK_CHARS

            chunk_text = para[:split_point].strip()
            if chunk_text:
                chunks.append(self._make_chunk(chunk_text, title, section_path, page_numbers, metadata, idx))
                idx += 1

            para = para[split_point:].strip()

        return para, idx

    def _compute_overlap(self, current_text: str, next_para: str, overlap_chars: int) -> str:
        """Compute overlapping text for chunk continuity."""
        if overlap_chars and len(current_text) > overlap_chars:
            return f"{current_text[-overlap_chars:]}\n\n{next_para}"
        return next_para

    def _make_chunk(
        self,
        content: str,
        title: str,
        section_path: str,
        page_numbers: list[int],
        metadata: dict,
        chunk_index: int,
    ) -> Chunk:
        """Create a Chunk with computed hash and token count."""
        return Chunk(
            title=title,
            content=content,
            chunk_index=chunk_index,
            section_path=section_path,
            metadata={
                "page_numbers": page_numbers,
                "section_path": section_path,
                **metadata,
            },
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            token_count=int(len(content) / CHARS_PER_TOKEN),
        )

    def _sanitize_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Run content sanitizer on each chunk."""
        sanitized = []
        for chunk in chunks:
            clean_content, events = sanitize_content(chunk.content, self.source.name)
            self.stats["sanitization_events"] += len(events)

            if clean_content:
                # Recompute hash after sanitization
                chunk.content = clean_content
                chunk.content_hash = hashlib.sha256(clean_content.encode()).hexdigest()
                chunk.token_count = int(len(clean_content) / CHARS_PER_TOKEN)
                sanitized.append(chunk)

        return sanitized

    def _deduplicate(self, chunks: list[Chunk]) -> list[Chunk]:
        """Remove chunks whose content_hash already exists for this source."""
        existing_hashes = set(
            KnowledgeDocument.objects.filter(source=self.source).values_list("content_hash", flat=True)
        )

        new_chunks = []
        for chunk in chunks:
            if chunk.content_hash in existing_hashes:
                self.stats["chunks_deduplicated"] += 1
            else:
                new_chunks.append(chunk)

        return new_chunks

    def _embed_and_store(self, chunks: list[Chunk]):
        """Embed chunks and store in database.

        Embeds one chunk at a time (EMBEDDING_BATCH_SIZE=1) to avoid
        exceeding Ollama's context window limits.
        """
        embedding_client = get_embedding_client()
        total_batches = (len(chunks) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE

        for batch_start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[batch_start : batch_start + EMBEDDING_BATCH_SIZE]
            texts = [c.content for c in batch]

            try:
                embeddings = embedding_client.embed_batch_sync(texts)
            except Exception:
                logger.exception("Failed to embed chunk at index %d", batch_start)
                self.stats["errors"] += 1
                continue

            if len(embeddings) != len(batch):
                logger.error(
                    "Embedding count mismatch: got %d embeddings for %d chunks",
                    len(embeddings),
                    len(batch),
                )
                self.stats["errors"] += 1
                continue

            docs = []
            for chunk, embedding in zip(batch, embeddings, strict=True):
                docs.append(
                    KnowledgeDocument(
                        source=self.source,
                        title=chunk.title,
                        content=chunk.content,
                        chunk_index=chunk.chunk_index,
                        chunk_metadata=chunk.metadata,
                        embedding=embedding,
                        token_count=chunk.token_count,
                        content_hash=chunk.content_hash,
                    )
                )

            created = KnowledgeDocument.objects.bulk_create(docs, ignore_conflicts=True)
            self.stats["chunks_created"] += len(created)

            # Log progress every 50 chunks to avoid log spam
            batch_num = batch_start // EMBEDDING_BATCH_SIZE + 1
            if batch_num % 50 == 0 or batch_num == total_batches:
                logger.info(
                    "Embedded %d/%d chunks for %s",
                    min(batch_start + EMBEDDING_BATCH_SIZE, len(chunks)),
                    len(chunks),
                    self.source.name,
                )

    def _update_search_vectors(self):
        """Populate tsvector search_vector for full-text search."""
        KnowledgeDocument.objects.filter(
            source=self.source,
            search_vector=None,
        ).update(
            search_vector=SearchVector("content", config="english"),
        )
