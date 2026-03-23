"""Tests for TranslationService — LLM-powered clinical translation."""

from unittest.mock import AsyncMock, patch

import pytest
from django.core.cache import cache

from apps.agents.translation import TranslationService


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear locmem cache between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns a canned translation."""
    client = AsyncMock()
    client.generate.return_value = {
        "content": "Hola, como estas?",
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
        "model": "mock",
        "finish_reason": "stop",
    }
    return client


class TestTranslationService:
    def test_translate_same_language_noop(self):
        """source==target returns original text without calling LLM."""
        result = TranslationService.translate("Hello", "en", "en")
        assert result == "Hello"

    def test_translate_returns_text(self, mock_llm_client):
        """Successful translation returns translated text."""
        with patch("apps.agents.llm_client.get_llm_client", return_value=mock_llm_client):
            result = TranslationService.translate("Hello, how are you?", "en", "es")
        assert result == "Hola, como estas?"
        mock_llm_client.generate.assert_called_once()

    def test_translate_failure_returns_none(self):
        """LLM failure returns None."""
        client = AsyncMock()
        client.generate.side_effect = Exception("LLM unavailable")
        with patch("apps.agents.llm_client.get_llm_client", return_value=client):
            result = TranslationService.translate("Hello", "en", "es")
        assert result is None

    def test_translate_cache_hit(self, mock_llm_client):
        """Cached translation returned without a second LLM call."""
        with patch("apps.agents.llm_client.get_llm_client", return_value=mock_llm_client):
            result1 = TranslationService.translate("Hello, how are you?", "en", "es")
            result2 = TranslationService.translate("Hello, how are you?", "en", "es")

        assert result1 == result2
        # LLM should only be called once — second call hits cache
        assert mock_llm_client.generate.call_count == 1

    def test_cache_key_generation(self):
        """Different texts produce different cache keys."""
        key1 = TranslationService._cache_key("Hello", "en", "es")
        key2 = TranslationService._cache_key("Goodbye", "en", "es")
        key3 = TranslationService._cache_key("Hello", "en", "fr")
        assert key1 != key2
        assert key1 != key3
        assert key1.startswith("translation:")

    def test_lang_name_lookup(self, settings):
        """_lang_name returns full language name from settings.LANGUAGES."""
        assert TranslationService._lang_name("en") == "English"
        assert TranslationService._lang_name("es") == "Spanish"
        # Unknown code returns the code itself
        assert TranslationService._lang_name("xx") == "xx"
