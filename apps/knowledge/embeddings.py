"""Embedding client for generating vector embeddings via Ollama.

Provides both sync and async interfaces:
- Sync methods (embed_sync, embed_batch_sync) for management commands
- Async methods (embed, embed_batch) for compatibility with existing code

Uses Qwen3-Embedding-4B (2000 dimensions, 40K token context) by default.
Supports instruction-aware embedding for improved retrieval accuracy.
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
    """Client for generating embeddings via Ollama API.

    Provides both sync and async interfaces. The sync interface uses fresh
    connections per request to avoid event loop issues in management commands.

    Supports instruction-aware embedding: pass an `instruction` string to
    prepend to each text before embedding. This improves retrieval accuracy
    for Qwen3-Embedding models by ~1-5%.
    """

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
        self.model = getattr(settings, "EMBEDDING_MODEL", "qwen3-embedding:4b")
        self.dimensions = getattr(settings, "EMBEDDING_DIMENSIONS", 2000)
        self._client = None
        self._initialized = True

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url.rstrip("/") + "/",
                timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    def _prepare_texts(self, texts: list[str], instruction: str | None = None) -> list[str]:
        """Prepend instruction to texts if provided.

        Ollama's /api/embed doesn't have a native instruction field,
        so we prepend the instruction text to each input string.
        """
        if not instruction:
            return texts
        return [f"{instruction}{t}" for t in texts]

    # -------------------------------------------------------------------------
    # Sync interface (for management commands, avoids event loop issues)
    # -------------------------------------------------------------------------

    def embed_sync(self, text: str, instruction: str | None = None) -> list[float]:
        """Generate embedding for a single text (sync version)."""
        result = self.embed_batch_sync([text], instruction=instruction)
        return result[0]

    def embed_batch_sync(self, texts: list[str], instruction: str | None = None) -> list[list[float]]:
        """Generate embeddings for a batch of texts (sync version).

        Uses a fresh httpx.Client per call to avoid event loop issues
        when called from Django management commands.
        """
        if not texts:
            return []

        prepared = self._prepare_texts(texts, instruction)
        url = f"{self.base_url.rstrip('/')}/api/embed"

        try:
            with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)) as sync_client:
                response = sync_client.post(
                    url,
                    json={"model": self.model, "input": prepared},
                    headers={"Content-Type": "application/json"},
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
            logger.error("Embedding HTTP error: %s", e.response.status_code)
            raise EmbeddingError(f"HTTP {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error("Embedding request error: %s", e)
            raise EmbeddingError(f"Request failed: {e}") from e

    # -------------------------------------------------------------------------
    # Async interface (for compatibility with existing async code and tests)
    # -------------------------------------------------------------------------

    async def embed(self, text: str, instruction: str | None = None) -> list[float]:
        """Generate embedding for a single text (async version)."""
        result = await self.embed_batch([text], instruction=instruction)
        return result[0]

    async def embed_batch(self, texts: list[str], instruction: str | None = None) -> list[list[float]]:
        """Generate embeddings for a batch of texts (async version)."""
        if not texts:
            return []

        prepared = self._prepare_texts(texts, instruction)

        try:
            response = await self.client.post(
                "api/embed",
                json={"model": self.model, "input": prepared},
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
            logger.error("Embedding HTTP error: %s", e.response.status_code)
            raise EmbeddingError(f"HTTP {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error("Embedding request error: %s", e)
            raise EmbeddingError(f"Request failed: {e}") from e

    async def close(self):
        """Close the async HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @classmethod
    def reset(cls):
        """Reset the singleton (for testing)."""
        cls._instance = None


class MockEmbeddingClient:
    """Mock embedding client for testing.

    Returns deterministic 2000-dimensional vectors based on text hash.
    Provides both sync and async interfaces for compatibility.
    """

    def __init__(self, dimensions: int | None = None):
        self.dimensions = dimensions or getattr(settings, "EMBEDDING_DIMENSIONS", 2000)
        self.call_count = 0
        self.last_texts: list[str] = []

    def _deterministic_vector(self, text: str) -> list[float]:
        """Generate a deterministic vector from text hash.

        Uses simple hash-based approach so identical texts always produce
        identical vectors, making tests predictable.
        """
        h = hash(text)
        vector = []
        for i in range(self.dimensions):
            val = ((h + i * 31) % 1000) / 1000.0
            vector.append(val * 2 - 1)
        return vector

    # Sync interface (used by ingestion pipeline)
    def embed_sync(self, text: str, instruction: str | None = None) -> list[float]:
        return self.embed_batch_sync([text], instruction=instruction)[0]

    def embed_batch_sync(self, texts: list[str], instruction: str | None = None) -> list[list[float]]:
        self.call_count += 1
        self.last_texts = texts
        return [self._deterministic_vector(t) for t in texts]

    # Async interface (for compatibility with async code and tests)
    async def embed(self, text: str, instruction: str | None = None) -> list[float]:
        result = await self.embed_batch([text], instruction=instruction)
        return result[0]

    async def embed_batch(self, texts: list[str], instruction: str | None = None) -> list[list[float]]:
        self.call_count += 1
        self.last_texts = texts
        return [self._deterministic_vector(t) for t in texts]

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
