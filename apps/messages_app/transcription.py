"""Transcription backends for voice-to-text.

Three-tier transcription following the LLMClient/MockLLMClient pattern:

    BaseTranscriptionClient.transcribe(audio_data, format) -> str
    ├── MockTranscriptionClient       — returns canned text (tests)
    ├── LocalWhisperClient            — faster-whisper, CPU (dev)
    └── RemoteTranscriptionClient     — OpenAI-compatible API (production)

Configuration via TRANSCRIPTION_BACKEND setting (dotted class path).
"""

import importlib
import logging
from functools import cache

from django.conf import settings

logger = logging.getLogger(__name__)


class BaseTranscriptionClient:
    """Abstract base for transcription backends."""

    def transcribe(self, audio_data, format="webm"):
        """Transcribe audio data to text.

        Args:
            audio_data: Bytes of audio data
            format: Audio format (webm, wav, mp3, etc.)

        Returns:
            Transcribed text string
        """
        raise NotImplementedError


class MockTranscriptionClient(BaseTranscriptionClient):
    """Mock transcription client for testing.

    Returns configurable canned text.
    """

    def __init__(self):
        self.call_count = 0
        self.last_audio_data = None
        self.response_text = "This is a mock transcription of the voice message."

    def transcribe(self, audio_data, format="webm"):
        self.call_count += 1
        self.last_audio_data = audio_data

        if not audio_data:
            return ""

        return self.response_text


class LocalWhisperClient(BaseTranscriptionClient):
    """Local transcription via faster-whisper (CPU).

    Uses the tiny or base model for fast local transcription
    during development. No external API calls needed.
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
        self._model = None
        self._initialized = True

    @property
    def model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel

                model_size = getattr(settings, "WHISPER_MODEL_SIZE", "tiny")
                self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
                logger.info("Loaded faster-whisper model: %s", model_size)
            except ImportError:
                logger.warning("faster-whisper not installed, falling back to MockTranscriptionClient")
                return None
        return self._model

    def transcribe(self, audio_data, format="webm"):
        if not audio_data:
            return ""

        if self.model is None:
            # Fallback to mock if faster-whisper not installed
            return MockTranscriptionClient().transcribe(audio_data, format)

        import tempfile

        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=True) as f:
            f.write(audio_data)
            f.flush()

            segments, info = self.model.transcribe(f.name, beam_size=5)
            text = " ".join(segment.text for segment in segments).strip()

        logger.info("Local transcription complete: %d chars", len(text))
        return text


class RemoteTranscriptionClient(BaseTranscriptionClient):
    """Remote transcription via OpenAI-compatible API.

    Sends audio to /v1/audio/transcriptions endpoint.
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
        self.api_key = getattr(settings, "TRANSCRIPTION_API_KEY", None)
        self.base_url = getattr(settings, "TRANSCRIPTION_BASE_URL", "https://api.openai.com/v1")
        self.model = getattr(settings, "TRANSCRIPTION_MODEL", "whisper-1")
        self._initialized = True

    def transcribe(self, audio_data, format="webm"):
        if not audio_data:
            return ""

        if not self.api_key:
            raise ValueError("TRANSCRIPTION_API_KEY not configured")

        import httpx

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url.rstrip('/')}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (f"audio.{format}", audio_data, f"audio/{format}")},
                data={"model": self.model},
            )
            response.raise_for_status()
            result = response.json()

        text = result.get("text", "").strip()
        logger.info("Remote transcription complete: %d chars", len(text))
        return text


@cache
def _import_transcription_class(dotted_path):
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_transcription_client():
    """Get the configured transcription client.

    Reads from settings.TRANSCRIPTION_BACKEND.
    """
    dotted_path = getattr(
        settings,
        "TRANSCRIPTION_BACKEND",
        "apps.messages_app.transcription.MockTranscriptionClient",
    )
    client_class = _import_transcription_class(dotted_path)
    return client_class()
