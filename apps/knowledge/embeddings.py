"""Embedding client for generating vector embeddings via Ollama.

Follows the singleton + async httpx pattern from apps/agents/llm_client.py.
Uses nomic-embed-text (768 dimensions) by default.
"""

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Base exception for embedding errors."""


class EmbeddingTimeoutError(EmbeddingError):
    """Raised when embedding request times out."""


class EmbeddingClient:
    """Client for generating embeddings via Ollama API."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.base_url = getattr(settings, "EMBEDDING_BASE_URL", "http://localhost:11434")
        self.model = getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text")
        self.dimensions = getattr(settings, "EMBEDDING_DIMENSIONS", 768)
        self._client = None
        self._initialized = True

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url.rstrip("/") + "/",
                timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            List of floats (embedding vector).

        Raises:
            EmbeddingError: If the embedding request fails.
            EmbeddingTimeoutError: If the request times out.
        """
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            EmbeddingError: If the embedding request fails.
            EmbeddingTimeoutError: If the request times out.
        """
        if not texts:
            return []

        try:
            response = await self.client.post(
                "api/embed",
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()

            embeddings = data.get("embeddings", [])
            if len(embeddings) != len(texts):
                raise EmbeddingError(f"Expected {len(texts)} embeddings, got {len(embeddings)}")

            return embeddings

        except httpx.TimeoutException as e:
            logger.error("Embedding request timed out")
            raise EmbeddingTimeoutError("Embedding request timed out") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"Embedding HTTP error: {e.response.status_code}")
            raise EmbeddingError(f"HTTP {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error(f"Embedding request error: {e}")
            raise EmbeddingError(f"Request failed: {e}") from e

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @classmethod
    def reset(cls):
        """Reset the singleton (for testing)."""
        cls._instance = None


class MockEmbeddingClient:
    """Mock embedding client for testing.

    Returns deterministic 768-dimensional vectors based on text hash.
    """

    def __init__(self, dimensions: int | None = None):
        self.dimensions = dimensions or getattr(settings, "EMBEDDING_DIMENSIONS", 768)
        self.call_count = 0
        self.last_texts: list[str] = []

    async def embed(self, text: str) -> list[float]:
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        self.last_texts = texts
        return [self._deterministic_vector(t) for t in texts]

    def _deterministic_vector(self, text: str) -> list[float]:
        """Generate a deterministic vector from text hash.

        Uses simple hash-based approach so identical texts always produce
        identical vectors, making tests predictable.
        """
        h = hash(text)
        vector = []
        for i in range(self.dimensions):
            # Create a deterministic float from hash + index
            val = ((h + i * 31) % 1000) / 1000.0
            # Normalize to [-1, 1] range
            vector.append(val * 2 - 1)
        return vector

    async def close(self):
        pass


def get_embedding_client() -> EmbeddingClient | MockEmbeddingClient:
    """Get the embedding client based on settings.

    Returns MockEmbeddingClient when EMBEDDING_BACKEND is configured
    (e.g., in test settings).
    """
    backend = getattr(settings, "EMBEDDING_BACKEND", None)
    if backend and "Mock" in backend:
        return MockEmbeddingClient()
    return EmbeddingClient()
