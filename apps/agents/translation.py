"""Translation service using the LLM for clinical communication translation."""

import hashlib
import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TranslationService:
    """Translates clinical communications between languages using LLM."""

    CACHE_TTL = 3600  # 1 hour
    CACHE_PREFIX = "translation:"

    @staticmethod
    def translate(text: str, source_lang: str, target_lang: str) -> str | None:
        """Translate text between languages.

        Returns translated text, or None if translation fails.
        Uses cache for repeated phrases.
        """
        if source_lang == target_lang:
            return text

        if not text or not text.strip():
            return text

        # Check cache
        cache_key = TranslationService._cache_key(text, source_lang, target_lang)
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            from apps.agents.llm_client import get_llm_client

            client = get_llm_client()

            source_name = TranslationService._lang_name(source_lang)
            target_name = TranslationService._lang_name(target_lang)

            prompt = (
                f"Translate the following medical communication from "
                f"{source_name} to {target_name}. "
                f"Preserve the tone, warmth, and clinical accuracy. "
                f"Do not add or remove information. "
                f"Return ONLY the translated text, nothing else.\n\n"
                f"{text}"
            )

            messages = [{"role": "user", "content": prompt}]
            response = async_to_sync(client.generate)(messages)
            translated = response["content"].strip()

            # Cache the result
            cache.set(cache_key, translated, TranslationService.CACHE_TTL)

            return translated
        except Exception:
            logger.exception("Translation failed: %s -> %s", source_lang, target_lang)
            return None

    @staticmethod
    def _cache_key(text: str, source: str, target: str) -> str:
        text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:12]  # noqa: S324
        return f"{TranslationService.CACHE_PREFIX}{source}:{target}:{text_hash}"

    @staticmethod
    def _lang_name(code: str) -> str:
        lang_names = dict(settings.LANGUAGES)
        return lang_names.get(code, code)
