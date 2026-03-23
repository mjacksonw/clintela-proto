"""LLM Client abstraction for Ollama Cloud integration via LangChain."""

import asyncio
import json
import logging
from typing import Any

import httpx
from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM errors."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when LLM rate limit is hit."""

    pass


class LLMResponseError(LLMError):
    """Raised when LLM returns invalid response."""

    pass


class LLMClient:
    """Client for Ollama Cloud LLM API using LangChain ChatOllama.

    Provides retry logic, error handling, and automatic LangSmith tracing
    when LANGSMITH_TRACING=true is set in the environment.
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure single LLM client instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the LLM client."""
        if self._initialized:
            return

        self.api_key = getattr(settings, "OLLAMA_API_KEY", None)
        self.base_url = getattr(settings, "OLLAMA_BASE_URL", "https://api.ollama.com/v1")
        self.model = getattr(settings, "OLLAMA_MODEL", "llama3.2")
        self.timeout = getattr(settings, "OLLAMA_TIMEOUT", 30)
        self.max_retries = getattr(settings, "OLLAMA_MAX_RETRIES", 3)

        self._initialized = True

    def _make_model(self, temperature: float = 0.7, json_mode: bool = False) -> ChatOllama:
        """Create a ChatOllama instance with the given parameters.

        A fresh instance is created per call to support per-call temperature.
        ChatOllama construction is lightweight (no connection pooling).
        """
        # ChatOllama appends /api/chat itself, so we need the server root.
        # Strip trailing path components like /v1 or /api that were used by
        # the old httpx client.
        base = self.base_url.rstrip("/")
        for suffix in ("/v1", "/api"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "base_url": base,
            "temperature": temperature,
            "client_kwargs": {
                "headers": {"Authorization": f"Bearer {self.api_key}"},
                "timeout": float(self.timeout),
            },
        }
        if json_mode:
            kwargs["format"] = "json"
        return ChatOllama(**kwargs)

    @staticmethod
    def _convert_messages(
        messages: list[dict[str, str]],
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        """Convert list of dicts to LangChain message objects."""
        result: list[SystemMessage | HumanMessage | AIMessage] = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                result.append(SystemMessage(content=content))
            elif role == "assistant":
                result.append(AIMessage(content=content))
            else:
                result.append(HumanMessage(content=content))
        return result

    @staticmethod
    def _parse_response(response: AIMessage) -> dict[str, Any]:
        """Extract content, usage, model, and finish_reason from AIMessage."""
        meta = response.response_metadata or {}
        return {
            "content": response.content,
            "usage": {
                "prompt_tokens": meta.get("prompt_eval_count", 0),
                "completion_tokens": meta.get("eval_count", 0),
            },
            "model": meta.get("model", ""),
            "finish_reason": "stop" if meta.get("done") else meta.get("done_reason"),
        }

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a response from the LLM with retry logic.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional JSON schema for structured output

        Returns:
            Dict containing 'content', 'usage', 'model', and 'finish_reason' keys

        Raises:
            LLMTimeoutError: If request times out after retries
            LLMRateLimitError: If rate limit is hit
            LLMResponseError: If response is invalid
        """
        if not self.api_key:
            raise LLMError("OLLAMA_API_KEY not configured")

        json_mode = response_format is not None
        model = self._make_model(temperature=temperature, json_mode=json_mode)
        lc_messages = self._convert_messages(messages)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await model.ainvoke(lc_messages)
                return self._parse_response(response)

            except httpx.TimeoutException:
                last_error = LLMTimeoutError(f"Request timed out after {self.timeout}s")
                logger.warning(
                    f"LLM request timed out (attempt {attempt + 1}/{self.max_retries}, limit={self.timeout}s)"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(min(2 * (2**attempt), 10))
                continue
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    last_error = LLMRateLimitError("Rate limit exceeded")
                    logger.warning(f"LLM rate limit hit (attempt {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(min(2 * (2**attempt), 10))
                    continue
                logger.error(f"LLM HTTP error: {e.response.status_code} - {e.response.text}")
                raise LLMResponseError(f"HTTP {e.response.status_code}: {e.response.text}") from e
            except httpx.RequestError as e:
                logger.error(f"LLM request error: {e}")
                raise LLMError(f"Request failed: {e}") from e

        # If we get here, all retries failed
        raise last_error or LLMError("All retries failed")

    async def generate_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        """Generate a JSON response from the LLM.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Parsed JSON dict

        Raises:
            LLMResponseError: If response is not valid JSON
        """
        response = await self.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        content = response["content"].strip()

        # Try to extract JSON from markdown code blocks (safety net)
        if content.startswith("```json"):
            content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
        elif content.startswith("```"):
            content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM: {content}")
            raise LLMResponseError(f"Invalid JSON: {e}") from e

    async def close(self):
        """No-op — ChatOllama manages its own connections."""
        pass


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, responses: dict[str, Any] | None = None):
        """Initialize with optional predefined responses.

        Args:
            responses: Dict mapping prompt patterns to responses
        """
        self.responses = responses or {}
        self.call_count = 0
        self.last_messages = None

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mock generate method."""
        self.call_count += 1
        self.last_messages = messages

        # Extract the last user message for pattern matching
        last_message = messages[-1]["content"] if messages else ""

        # Check for predefined responses
        for pattern, response in self.responses.items():
            if pattern in last_message.lower():
                if isinstance(response, dict):
                    return {
                        "content": json.dumps(response),
                        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                        "model": "mock",
                        "finish_reason": "stop",
                    }
                return {
                    "content": str(response),
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                    "model": "mock",
                    "finish_reason": "stop",
                }

        # Default response
        return {
            "content": "This is a mock response for testing.",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            "model": "mock",
            "finish_reason": "stop",
        }

    async def generate_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        """Mock generate_json method."""
        response = await self.generate(messages, temperature, max_tokens)
        content = response["content"].strip()

        # Try to parse as JSON, fallback to dict with content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"response": content}

    async def close(self):
        """No-op close method."""
        pass


def get_llm_client() -> LLMClient:
    """Get the singleton LLM client instance."""
    return LLMClient()
