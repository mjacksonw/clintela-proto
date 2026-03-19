"""LLM Client abstraction for Ollama Cloud integration."""

import json
import logging
from typing import Any

import httpx
from django.conf import settings

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
            # Ensure trailing slash for proper URL path joining
            base_url = self.base_url.rstrip("/") + "/"
            # Use explicit timeout config for cloud LLMs which can be slow
            timeout_config = httpx.Timeout(
                connect=10.0,
                read=float(self.timeout),  # Main timeout for LLM response
                write=10.0,
                pool=10.0,
            )
            self._client = httpx.AsyncClient(
                base_url=base_url,
                timeout=timeout_config,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def generate(  # noqa: C901
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
            Dict containing 'content', 'usage', and 'model' keys

        Raises:
            LLMTimeoutError: If request times out after retries
            LLMRateLimitError: If rate limit is hit
            LLMResponseError: If response is invalid
        """
        if not self.api_key:
            raise LLMError("OLLAMA_API_KEY not configured")

        # Determine endpoint based on base URL
        base_url_normalized = self.base_url.rstrip("/")

        # Check if this is Ollama Cloud (ollama.com/api) vs OpenAI-compatible
        is_ollama_cloud = "ollama.com" in base_url_normalized or (
            "/api" in base_url_normalized and not base_url_normalized.endswith("/v1")
        )
        if is_ollama_cloud:
            # Use relative path (no leading slash) since base_url includes /api
            endpoint = "chat" if base_url_normalized.endswith("/api") else "api/chat"
            # Ollama format doesn't use response_format in payload
            ollama_payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
            }
            if response_format:
                ollama_payload["format"] = "json"
            payload = ollama_payload
        else:
            # OpenAI-compatible format
            endpoint = "chat/completions"
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            if response_format:
                payload["response_format"] = response_format

        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(endpoint, json=payload)
                response.raise_for_status()

                # Parse response
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse LLM response: {e}")
                    raise LLMResponseError("Invalid JSON response") from e

                # Parse response based on API format
                if "choices" in data:
                    # OpenAI-compatible format
                    if not data["choices"]:
                        logger.error(f"Invalid LLM response structure: {data}")
                        raise LLMResponseError("Invalid response structure")
                    return {
                        "content": data["choices"][0]["message"]["content"],
                        "usage": data.get("usage", {}),
                        "model": data.get("model", self.model),
                        "finish_reason": data["choices"][0].get("finish_reason"),
                    }
                elif "message" in data:
                    # Ollama native format
                    return {
                        "content": data["message"]["content"],
                        "usage": data.get("prompt_eval_count") or data.get("usage", {}),
                        "model": data.get("model", self.model),
                        "finish_reason": "stop" if data.get("done") else None,
                    }
                else:
                    logger.error(f"Invalid LLM response structure: {data}")
                    raise LLMResponseError("Invalid response structure")

            except httpx.TimeoutException:
                last_error = LLMTimeoutError(f"Request timed out after {self.timeout}s")
                logger.warning(f"LLM request timed out (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    import asyncio

                    await asyncio.sleep(min(2 * (2**attempt), 10))  # Exponential backoff
                continue
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    last_error = LLMRateLimitError("Rate limit exceeded")
                    logger.warning(f"LLM rate limit hit (attempt {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        import asyncio

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
