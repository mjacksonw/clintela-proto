"""Tests for LLM client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from apps.agents.llm_client import (
    LLMClient,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    MockLLMClient,
    get_llm_client,
)


def _make_ai_message(content="Test response", done=True, model="test-model", **extra_meta):
    """Helper to create AIMessage with Ollama-style response_metadata."""
    meta = {"done": done, "model": model, "prompt_eval_count": 10, "eval_count": 5}
    meta.update(extra_meta)
    return AIMessage(content=content, response_metadata=meta)


class TestLLMClient:
    """Tests for LLMClient."""

    @pytest.fixture
    def llm_client(self):
        """Create LLM client for testing."""
        client = LLMClient()
        client.api_key = "test-key"  # pragma: allowlist secret
        return client

    @pytest.mark.asyncio
    @patch("apps.agents.llm_client.ChatOllama")
    async def test_generate_success(self, mock_chat_ollama_cls, llm_client):
        """Test successful generation."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=_make_ai_message())
        mock_chat_ollama_cls.return_value = mock_model

        result = await llm_client.generate(
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert result["content"] == "Test response"
        assert result["finish_reason"] == "stop"
        assert result["model"] == "test-model"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 5

    @pytest.mark.asyncio
    async def test_generate_raises_on_missing_api_key(self, llm_client):
        """Test generation fails without API key."""
        llm_client.api_key = None

        with pytest.raises(LLMError) as exc_info:
            await llm_client.generate(messages=[{"role": "user", "content": "Hello"}])

        assert "OLLAMA_API_KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("apps.agents.llm_client.ChatOllama")
    async def test_generate_raises_on_timeout(self, mock_chat_ollama_cls, llm_client):
        """Test timeout raises LLMTimeoutError."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(side_effect=httpx.TimeoutException("Connection timeout"))
        mock_chat_ollama_cls.return_value = mock_model

        with pytest.raises(LLMTimeoutError):
            await llm_client.generate(messages=[{"role": "user", "content": "Hello"}])

    @pytest.mark.asyncio
    @patch("apps.agents.llm_client.ChatOllama")
    async def test_generate_raises_on_rate_limit(self, mock_chat_ollama_cls, llm_client):
        """Test rate limit raises LLMRateLimitError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Rate limited",
                request=MagicMock(),
                response=mock_response,
            )
        )
        mock_chat_ollama_cls.return_value = mock_model

        with pytest.raises(LLMRateLimitError):
            await llm_client.generate(messages=[{"role": "user", "content": "Hello"}])

    @pytest.mark.asyncio
    @patch("apps.agents.llm_client.ChatOllama")
    async def test_generate_retries_on_failure(self, mock_chat_ollama_cls, llm_client):
        """Test retry logic works."""
        call_count = 0

        async def mock_ainvoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            return _make_ai_message(content="Success")

        mock_model = AsyncMock()
        mock_model.ainvoke = mock_ainvoke
        mock_chat_ollama_cls.return_value = mock_model

        result = await llm_client.generate(messages=[{"role": "user", "content": "Hello"}])

        assert result["content"] == "Success"
        assert call_count == 3

    @pytest.mark.asyncio
    @patch("apps.agents.llm_client.ChatOllama")
    async def test_generate_json_parses_response(self, mock_chat_ollama_cls, llm_client):
        """Test generate_json parses JSON from markdown."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=_make_ai_message(content='```json\n{"key": "value"}\n```'))
        mock_chat_ollama_cls.return_value = mock_model

        result = await llm_client.generate_json(messages=[{"role": "user", "content": "Hello"}])

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    @patch("apps.agents.llm_client.ChatOllama")
    async def test_generate_json_invalid_content(self, mock_chat_ollama_cls, llm_client):
        """Test generate_json raises LLMResponseError on invalid JSON."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=_make_ai_message(content="not valid json at all"))
        mock_chat_ollama_cls.return_value = mock_model

        with pytest.raises(LLMResponseError, match="Invalid JSON"):
            await llm_client.generate_json(messages=[{"role": "user", "content": "Hello"}])


class TestConvertMessages:
    """Tests for message conversion."""

    def test_converts_all_roles(self):
        """Test system/user/assistant dicts map to correct LangChain types."""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        result = LLMClient._convert_messages(messages)

        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "You are helpful"
        assert isinstance(result[1], HumanMessage)
        assert result[1].content == "Hello"
        assert isinstance(result[2], AIMessage)
        assert result[2].content == "Hi there"

    def test_unknown_role_defaults_to_human(self):
        """Test unknown roles are treated as HumanMessage."""
        messages = [{"role": "tool", "content": "result"}]
        result = LLMClient._convert_messages(messages)
        assert isinstance(result[0], HumanMessage)


class TestParseResponse:
    """Tests for response parsing."""

    def test_parses_complete_metadata(self):
        """Test full response_metadata extraction."""
        ai_msg = _make_ai_message(
            content="Hello",
            done=True,
            model="llama3.2",
            prompt_eval_count=50,
            eval_count=20,
        )

        result = LLMClient._parse_response(ai_msg)

        assert result["content"] == "Hello"
        assert result["model"] == "llama3.2"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] == 50
        assert result["usage"]["completion_tokens"] == 20

    def test_handles_missing_metadata(self):
        """Test graceful handling when response_metadata is empty."""
        ai_msg = AIMessage(content="Hello", response_metadata={})

        result = LLMClient._parse_response(ai_msg)

        assert result["content"] == "Hello"
        assert result["model"] == ""
        assert result["usage"]["prompt_tokens"] == 0
        assert result["usage"]["completion_tokens"] == 0

    def test_done_false_uses_done_reason(self):
        """Test finish_reason when done=False."""
        ai_msg = AIMessage(
            content="...",
            response_metadata={"done": False, "done_reason": "length"},
        )

        result = LLMClient._parse_response(ai_msg)
        assert result["finish_reason"] == "length"


class TestMockLLMClient:
    """Tests for MockLLMClient."""

    @pytest.mark.asyncio
    async def test_returns_predefined_response(self):
        """Test mock returns predefined responses."""
        client = MockLLMClient(
            responses={
                "hello": "Hi there!",
            }
        )

        result = await client.generate(
            [
                {"role": "user", "content": "hello"},
            ]
        )

        assert result["content"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_returns_default_response(self):
        """Test mock returns default response for unknown patterns."""
        client = MockLLMClient()

        result = await client.generate(
            [
                {"role": "user", "content": "unknown query"},
            ]
        )

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
        client = MockLLMClient(
            responses={
                "query": {"result": "success"},
            }
        )

        result = await client.generate_json(
            [
                {"role": "user", "content": "query"},
            ]
        )

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
