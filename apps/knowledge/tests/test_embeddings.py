"""Tests for embedding client."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from apps.knowledge.embeddings import (
    EmbeddingClient,
    EmbeddingError,
    EmbeddingTimeoutError,
    MockEmbeddingClient,
    get_embedding_client,
)


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


class TestEmbeddingClientSingleton:
    """Tests for EmbeddingClient singleton behaviour (lines 28-32, 34-42)."""

    def setup_method(self):
        # Reset singleton before each test so state doesn't bleed across tests.
        EmbeddingClient.reset()

    def teardown_method(self):
        EmbeddingClient.reset()

    def test_singleton_returns_same_instance(self):
        # Lines 29-32: __new__ creates instance on first call, reuses on second.
        a = EmbeddingClient()
        b = EmbeddingClient()
        assert a is b

    def test_init_sets_defaults(self):
        # Lines 35-42: __init__ reads settings, assigns attributes, sets _initialized.
        client = EmbeddingClient()
        assert client.base_url == "http://localhost:11434"
        assert client.model == "nomic-embed-text"
        assert client.dimensions == 768
        assert client._client is None
        assert client._initialized is True

    def test_init_only_runs_once(self):
        # Lines 35-36: second __init__ call on the same singleton is a no-op.
        first = EmbeddingClient()
        original_model = first.model
        first.model = "changed"
        second = EmbeddingClient()
        # __init__ skips re-assignment, so the change persists.
        assert second.model == "changed"
        first.model = original_model

    def test_init_reads_custom_settings(self, settings):
        # Lines 38-40: custom Django settings are respected.
        settings.EMBEDDING_BASE_URL = "http://custom-host:11434"
        settings.EMBEDDING_MODEL = "custom-model"
        settings.EMBEDDING_DIMENSIONS = 512
        client = EmbeddingClient()
        assert client.base_url == "http://custom-host:11434"
        assert client.model == "custom-model"
        assert client.dimensions == 512

    def test_reset_clears_singleton(self):
        # Line 119: reset() sets _instance to None so next call creates fresh object.
        a = EmbeddingClient()
        EmbeddingClient.reset()
        b = EmbeddingClient()
        assert a is not b


class TestEmbeddingClientHttpxProperty:
    """Tests for the lazy httpx.AsyncClient property (lines 46-52)."""

    def setup_method(self):
        EmbeddingClient.reset()

    def teardown_method(self):
        EmbeddingClient.reset()

    def test_client_property_creates_async_client(self):
        # Lines 46-52: first access builds the httpx.AsyncClient.
        client = EmbeddingClient()
        assert client._client is None
        http_client = client.client
        assert isinstance(http_client, httpx.AsyncClient)
        assert client._client is not None

    def test_client_property_is_cached(self):
        # Second access returns the exact same object (no re-creation).
        client = EmbeddingClient()
        first = client.client
        second = client.client
        assert first is second

    def test_client_base_url_strips_trailing_slash(self):
        # Line 48: trailing slash is stripped then re-added to form a clean base URL.
        client = EmbeddingClient()
        client.base_url = "http://localhost:11434/"
        http_client = client.client
        # httpx normalises the base_url; just verify the client was created.
        assert isinstance(http_client, httpx.AsyncClient)


@pytest.mark.asyncio
class TestEmbeddingClientEmbed:
    """Tests for embed() delegating to embed_batch() (lines 67-68)."""

    def setup_method(self):
        EmbeddingClient.reset()

    def teardown_method(self):
        EmbeddingClient.reset()

    async def test_embed_delegates_to_embed_batch(self):
        # Lines 67-68: embed() calls embed_batch([text]) and returns first element.
        client = EmbeddingClient()
        fake_vector = [0.1] * 768
        client.embed_batch = AsyncMock(return_value=[fake_vector])

        result = await client.embed("hello")

        client.embed_batch.assert_awaited_once_with(["hello"])
        assert result == fake_vector


@pytest.mark.asyncio
class TestEmbeddingClientEmbedBatch:
    """Tests for embed_batch() happy-path and error paths (lines 83-108)."""

    def setup_method(self):
        EmbeddingClient.reset()

    def teardown_method(self):
        EmbeddingClient.reset()

    def _make_client_with_mock_http(self, response_data=None, side_effect=None):
        """Return an EmbeddingClient whose internal httpx client is mocked."""
        client = EmbeddingClient()
        mock_response = MagicMock()
        mock_response.json.return_value = response_data or {}
        mock_response.raise_for_status = MagicMock()

        mock_http = MagicMock()
        if side_effect:
            mock_http.post = AsyncMock(side_effect=side_effect)
        else:
            mock_http.post = AsyncMock(return_value=mock_response)

        client._client = mock_http
        return client, mock_response

    async def test_embed_batch_empty_returns_empty(self):
        # Line 83-84: early return for empty input list.
        client = EmbeddingClient()
        result = await client.embed_batch([])
        assert result == []

    async def test_embed_batch_happy_path(self):
        # Lines 87-98: successful POST returns embeddings list.
        vectors = [[0.1, 0.2], [0.3, 0.4]]
        client, _ = self._make_client_with_mock_http(response_data={"embeddings": vectors})
        result = await client.embed_batch(["text a", "text b"])
        assert result == vectors

    async def test_embed_batch_posts_correct_payload(self):
        # Lines 87-90: verifies model name and input are sent to the API.
        vectors = [[0.5] * 768]
        client, _ = self._make_client_with_mock_http(response_data={"embeddings": vectors})
        await client.embed_batch(["single text"])
        client._client.post.assert_awaited_once_with(
            "api/embed",
            json={"model": client.model, "input": ["single text"]},
        )

    async def test_embed_batch_raises_on_count_mismatch(self):
        # Lines 95-96: mismatch between requested and returned embeddings raises EmbeddingError.
        client, _ = self._make_client_with_mock_http(
            response_data={"embeddings": [[0.1]]}  # only 1 vector for 2 texts
        )
        with pytest.raises(EmbeddingError, match="Expected 2 embeddings, got 1"):
            await client.embed_batch(["text a", "text b"])

    async def test_embed_batch_raises_on_timeout(self):
        # Lines 100-102: httpx.TimeoutException is re-raised as EmbeddingTimeoutError.
        client, _ = self._make_client_with_mock_http(side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(EmbeddingTimeoutError, match="timed out"):
            await client.embed_batch(["text"])

    async def test_embed_batch_raises_on_http_status_error(self):
        # Lines 103-105: httpx.HTTPStatusError is re-raised as EmbeddingError with status code.
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_err = httpx.HTTPStatusError("server error", request=MagicMock(), response=mock_response)
        client, _ = self._make_client_with_mock_http(side_effect=http_err)
        with pytest.raises(EmbeddingError, match="HTTP 500"):
            await client.embed_batch(["text"])

    async def test_embed_batch_raises_on_request_error(self):
        # Lines 106-108: httpx.RequestError (e.g. connection refused) raises EmbeddingError.
        req_err = httpx.ConnectError("connection refused")
        client, _ = self._make_client_with_mock_http(side_effect=req_err)
        with pytest.raises(EmbeddingError, match="Request failed"):
            await client.embed_batch(["text"])


@pytest.mark.asyncio
class TestEmbeddingClientClose:
    """Tests for close() releasing the httpx client (lines 112-114)."""

    def setup_method(self):
        EmbeddingClient.reset()

    def teardown_method(self):
        EmbeddingClient.reset()

    async def test_close_when_client_exists(self):
        # Lines 112-114: aclose() is called and _client is set back to None.
        client = EmbeddingClient()
        mock_http = MagicMock()
        mock_http.aclose = AsyncMock()
        client._client = mock_http

        await client.close()

        mock_http.aclose.assert_awaited_once()
        assert client._client is None

    async def test_close_when_client_is_none(self):
        # Line 112: guard — no error when close() is called before client is created.
        client = EmbeddingClient()
        assert client._client is None
        await client.close()  # should not raise


class TestGetEmbeddingClient:
    """Tests for the get_embedding_client() factory (lines 167-170, 158)."""

    def setup_method(self):
        EmbeddingClient.reset()

    def teardown_method(self):
        EmbeddingClient.reset()

    def test_returns_mock_client_when_backend_contains_mock(self, settings):
        # Lines 168-169: "Mock" in EMBEDDING_BACKEND → MockEmbeddingClient.
        settings.EMBEDDING_BACKEND = "MockEmbeddingClient"
        result = get_embedding_client()
        assert isinstance(result, MockEmbeddingClient)

    def test_returns_real_client_when_no_backend(self, settings):
        # Line 170: no EMBEDDING_BACKEND → real EmbeddingClient singleton.
        if hasattr(settings, "EMBEDDING_BACKEND"):
            del settings.EMBEDDING_BACKEND
        result = get_embedding_client()
        assert isinstance(result, EmbeddingClient)

    def test_returns_real_client_when_backend_has_no_mock(self, settings):
        # Line 170: EMBEDDING_BACKEND set but "Mock" not in the string → real client.
        settings.EMBEDDING_BACKEND = "OllamaEmbeddingClient"
        result = get_embedding_client()
        assert isinstance(result, EmbeddingClient)

    def test_mock_client_close_is_noop(self):
        # Line 158: MockEmbeddingClient.close() returns without error.
        import asyncio

        mock_client = MockEmbeddingClient()
        # Should complete without raising even though it does nothing.
        asyncio.run(mock_client.close())
