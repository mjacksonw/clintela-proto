"""Tests for LLM client."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from apps.agents.llm_client import (
    LLMClient,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    MockLLMClient,
    get_llm_client,
)


class TestLLMClient:
    """Tests for LLMClient."""

    @pytest.fixture
    def llm_client(self):
        """Create LLM client for testing."""
        client = LLMClient()
        client.api_key = "test-key"
        return client

    @pytest.mark.asyncio
    async def test_generate_success(self, llm_client):
        """Test successful generation."""
        mock_response = {
            "choices": [{
                "message": {"content": "Test response"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "test-model",
        }

        # Create proper async mock - json() is an async method, raise_for_status is not
        mock_response_obj = AsyncMock()
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_response_obj.raise_for_status = lambda: None  # Not async

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        llm_client._client = mock_client

        result = await llm_client.generate(
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert result["content"] == "Test response"
        assert result["finish_reason"] == "stop"
        assert result["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_generate_raises_on_missing_api_key(self, llm_client):
        """Test generation fails without API key."""
        llm_client.api_key = None

        with pytest.raises(LLMError) as exc_info:
            await llm_client.generate(messages=[{"role": "user", "content": "Hello"}])

        assert "OLLAMA_API_KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_raises_on_timeout(self, llm_client):
        """Test timeout raises LLMTimeoutError."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Connection timeout"))
        llm_client._client = mock_client

        with pytest.raises(LLMTimeoutError):
            await llm_client.generate(messages=[{"role": "user", "content": "Hello"}])

    @pytest.mark.asyncio
    async def test_generate_raises_on_rate_limit(self, llm_client):
        """Test rate limit raises LLMRateLimitError."""
        mock_response = AsyncMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Rate limited",
                request=AsyncMock(),
                response=mock_response,
            )
        )
        llm_client._client = mock_client

        with pytest.raises(LLMRateLimitError):
            await llm_client.generate(messages=[{"role": "user", "content": "Hello"}])

    @pytest.mark.asyncio
    async def test_generate_raises_on_invalid_json(self, llm_client):
        """Test invalid JSON response raises LLMResponseError."""
        mock_response_obj = AsyncMock()
        mock_response_obj.json = AsyncMock(side_effect=json.JSONDecodeError("test", "doc", 0))
        mock_response_obj.raise_for_status = lambda: None  # Not async

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        llm_client._client = mock_client

        with pytest.raises(LLMResponseError):
            await llm_client.generate(messages=[{"role": "user", "content": "Hello"}])

    @pytest.mark.asyncio
    async def test_generate_retries_on_failure(self, llm_client):
        """Test retry logic works."""
        # Fail twice, then succeed
        call_count = 0
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            # Return successful response
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value={
                "choices": [{"message": {"content": "Success"}}],
            })
            mock_response_obj.raise_for_status = AsyncMock()
            return mock_response_obj

        mock_client = AsyncMock()
        mock_client.post = mock_post
        llm_client._client = mock_client

        result = await llm_client.generate(messages=[{"role": "user", "content": "Hello"}])

        assert result["content"] == "Success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_generate_json_parses_response(self, llm_client):
        """Test generate_json parses JSON from markdown."""
        mock_response_obj = AsyncMock()
        mock_response_obj.json = AsyncMock(return_value={
            "choices": [{"message": {"content": '```json\n{"key": "value"}\n```'}}],
        })
        mock_response_obj.raise_for_status = lambda: None  # Not async

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        llm_client._client = mock_client

        result = await llm_client.generate_json(messages=[{"role": "user", "content": "Hello"}])

        assert result == {"key": "value"}


class TestMockLLMClient:
    """Tests for MockLLMClient."""

    @pytest.mark.asyncio
    async def test_returns_predefined_response(self):
        """Test mock returns predefined responses."""
        client = MockLLMClient(responses={
            "hello": "Hi there!",
        })

        result = await client.generate([
            {"role": "user", "content": "hello"},
        ])

        assert result["content"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_returns_default_response(self):
        """Test mock returns default response for unknown patterns."""
        client = MockLLMClient()

        result = await client.generate([
            {"role": "user", "content": "unknown query"},
        ])

        assert "mock response" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_tracks_calls(self):
        """Test mock tracks call count."""
        client = MockLLMClient()

        await client.generate([{"role": "user", "content": "Hello"}])
        await client.generate([{"role": "user", "content": "Hello again"}])

        assert client.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_json_parses_dict_response(self):
        """Test generate_json handles dict responses."""
        client = MockLLMClient(responses={
            "query": {"result": "success"},
        })

        result = await client.generate_json([
            {"role": "user", "content": "query"},
        ])

        assert result == {"result": "success"}


class TestGetLLMClient:
    """Tests for get_llm_client factory."""

    def test_returns_singleton(self):
        """Test factory returns same instance."""
        client1 = get_llm_client()
        client2 = get_llm_client()

        assert client1 is client2

    def test_client_is_initialized(self):
        """Test client is properly initialized."""
        client = get_llm_client()
        assert client._initialized is True
