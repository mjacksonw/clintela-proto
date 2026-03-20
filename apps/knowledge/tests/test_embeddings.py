"""Tests for embedding client."""

import pytest

from apps.knowledge.embeddings import MockEmbeddingClient


@pytest.mark.asyncio
class TestMockEmbeddingClient:
    async def test_embed_returns_correct_dimensions(self):
        client = MockEmbeddingClient(dimensions=768)
        result = await client.embed("test text")
        assert len(result) == 768

    async def test_embed_batch_returns_correct_count(self):
        client = MockEmbeddingClient()
        texts = ["text one", "text two", "text three"]
        results = await client.embed_batch(texts)
        assert len(results) == 3
        assert all(len(v) == 768 for v in results)

    async def test_embed_batch_empty_input(self):
        client = MockEmbeddingClient()
        results = await client.embed_batch([])
        assert results == []

    async def test_deterministic_vectors(self):
        client = MockEmbeddingClient()
        v1 = await client.embed("same text")
        v2 = await client.embed("same text")
        assert v1 == v2

    async def test_different_texts_different_vectors(self):
        client = MockEmbeddingClient()
        v1 = await client.embed("text one")
        v2 = await client.embed("text two")
        assert v1 != v2

    async def test_tracks_call_count(self):
        client = MockEmbeddingClient()
        await client.embed("one")
        await client.embed("two")
        assert client.call_count == 2

    async def test_tracks_last_texts(self):
        client = MockEmbeddingClient()
        await client.embed_batch(["hello", "world"])
        assert client.last_texts == ["hello", "world"]

    async def test_values_in_range(self):
        client = MockEmbeddingClient()
        vector = await client.embed("test")
        assert all(-1 <= v <= 1 for v in vector)
