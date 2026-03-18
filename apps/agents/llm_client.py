"""LLM Client abstraction for Ollama Cloud integration."""

import json
import logging
from typing import Any

import httpx
from django.conf import settings
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

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
    """Client for Ollama Cloud LLM API with retry logic and error handling."""

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

        self._client = None
        self._initialized = True

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    @retry(
        retry=retry_if_exception_type((LLMTimeoutError, LLMRateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a response from the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional JSON schema for structured output

        Returns:
            Dict containing 'content', 'usage', and 'model' keys

        Raises:
            LLMTimeoutError: If request times out
            LLMRateLimitError: If rate limit is hit
            LLMResponseError: If response is invalid
        """
        if not self.api_key:
            raise LLMError("OLLAMA_API_KEY not configured")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        if response_format:
            payload["response_format"] = response_format

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            logger.error(f"LLM request timed out: {e}")
            raise LLMTimeoutError(f"Request timed out after {self.timeout}s") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("LLM rate limit hit")
                raise LLMRateLimitError("Rate limit exceeded") from e
            logger.error(f"LLM HTTP error: {e.response.status_code} - {e.response.text}")
            raise LLMResponseError(f"HTTP {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error(f"LLM request error: {e}")
            raise LLMError(f"Request failed: {e}") from e

        try:
            data = await response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise LLMResponseError("Invalid JSON response") from e

        if "choices" not in data or not data["choices"]:
            logger.error(f"Invalid LLM response structure: {data}")
            raise LLMResponseError("Invalid response structure")

        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "model": data.get("model", self.model),
            "finish_reason": data["choices"][0].get("finish_reason"),
        }

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
        )

        content = response["content"].strip()

        # Try to extract JSON from markdown code blocks
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
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


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
