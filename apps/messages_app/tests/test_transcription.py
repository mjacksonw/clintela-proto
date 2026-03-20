"""Tests for transcription backends."""

from unittest.mock import MagicMock, patch

from apps.messages_app.transcription import (
    BaseTranscriptionClient,
    LocalWhisperClient,
    MockTranscriptionClient,
    RemoteTranscriptionClient,
    _import_transcription_class,
    get_transcription_client,
)


class TestMockTranscriptionClient:
    def test_returns_canned_text(self):
        client = MockTranscriptionClient()
        result = client.transcribe(b"fake audio data", format="webm")
        assert result == "This is a mock transcription of the voice message."

    def test_tracks_call_count(self):
        client = MockTranscriptionClient()
        client.transcribe(b"data1")
        client.transcribe(b"data2")
        assert client.call_count == 2

    def test_stores_last_audio_data(self):
        client = MockTranscriptionClient()
        client.transcribe(b"my audio bytes")
        assert client.last_audio_data == b"my audio bytes"

    def test_empty_audio_returns_empty_string(self):
        client = MockTranscriptionClient()
        result = client.transcribe(b"")
        assert result == ""

    def test_none_audio_returns_empty_string(self):
        client = MockTranscriptionClient()
        result = client.transcribe(None)
        assert result == ""

    def test_custom_response_text(self):
        client = MockTranscriptionClient()
        client.response_text = "Custom transcription"
        result = client.transcribe(b"data")
        assert result == "Custom transcription"


class TestBaseTranscriptionClient:
    def test_transcribe_raises_not_implemented(self):
        import pytest

        client = BaseTranscriptionClient()
        with pytest.raises(NotImplementedError):
            client.transcribe(b"audio")


class TestLocalWhisperClient:
    def setup_method(self):
        # Reset the singleton between tests
        LocalWhisperClient._instance = None

    def test_singleton_pattern(self):
        client1 = LocalWhisperClient()
        client2 = LocalWhisperClient()
        assert client1 is client2

    def test_empty_audio_returns_empty_string(self):
        client = LocalWhisperClient()
        result = client.transcribe(b"")
        assert result == ""

    def test_none_audio_returns_empty_string(self):
        client = LocalWhisperClient()
        result = client.transcribe(None)
        assert result == ""

    def test_falls_back_to_mock_when_faster_whisper_not_installed(self):
        """When faster-whisper is not available, falls back to MockTranscriptionClient."""
        client = LocalWhisperClient()
        # Force model to None by patching the import
        with patch.dict("sys.modules", {"faster_whisper": None}):
            # Reset model so it will try to import
            client._model = None
            model = client.model
            # model will be None when import fails
            assert model is None

        # When model is None, transcribe should return mock result
        client._model = None
        with patch("builtins.__import__", side_effect=ImportError("No faster_whisper")):
            result = client.transcribe(b"audio data")
            # Should fall back to mock and return something (not empty)
            assert isinstance(result, str)

    def test_model_property_returns_none_on_import_error(self):
        """model property returns None when faster-whisper not installed."""
        client = LocalWhisperClient()
        client._model = None

        with patch.dict("sys.modules", {"faster_whisper": None}):
            # ImportError path via missing module
            import sys

            original = sys.modules.get("faster_whisper")
            try:
                sys.modules["faster_whisper"] = None
                model = client.model
                # None because import failed
                assert model is None
            finally:
                if original is None and "faster_whisper" in sys.modules:
                    del sys.modules["faster_whisper"]

    def test_transcribe_with_mock_fallback_when_model_none(self):
        """When model is None, transcription falls back to MockTranscriptionClient."""
        client = LocalWhisperClient()
        # Patch model property to return None
        with patch.object(type(client), "model", new_callable=lambda: property(lambda self: None)):
            result = client.transcribe(b"some audio data")
            # MockTranscriptionClient returns its canned text
            assert result == "This is a mock transcription of the voice message."

    def test_transcribe_with_whisper_model(self):
        """Test transcription when WhisperModel is available."""
        client = LocalWhisperClient()
        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())

        with patch.object(type(client), "model", new_callable=lambda: property(lambda self: mock_model)):
            result = client.transcribe(b"real audio data", format="wav")
            assert result == "Hello world"

    def test_transcribe_multiple_segments(self):
        """Test that multiple segments are joined."""
        client = LocalWhisperClient()
        mock_model = MagicMock()
        seg1 = MagicMock()
        seg1.text = "Hello"
        seg2 = MagicMock()
        seg2.text = " world"
        mock_model.transcribe.return_value = ([seg1, seg2], MagicMock())

        with patch.object(type(client), "model", new_callable=lambda: property(lambda self: mock_model)):
            result = client.transcribe(b"audio data")
            assert result == "Hello  world"


class TestRemoteTranscriptionClient:
    def setup_method(self):
        # Reset the singleton between tests
        RemoteTranscriptionClient._instance = None

    def test_singleton_pattern(self):
        client1 = RemoteTranscriptionClient()
        client2 = RemoteTranscriptionClient()
        assert client1 is client2

    def test_empty_audio_returns_empty_string(self):
        RemoteTranscriptionClient._instance = None
        client = RemoteTranscriptionClient()
        result = client.transcribe(b"")
        assert result == ""

    def test_none_audio_returns_empty_string(self):
        RemoteTranscriptionClient._instance = None
        client = RemoteTranscriptionClient()
        result = client.transcribe(None)
        assert result == ""

    def test_raises_when_no_api_key(self):
        import pytest

        RemoteTranscriptionClient._instance = None
        client = RemoteTranscriptionClient()
        client.api_key = None

        with pytest.raises(ValueError, match="TRANSCRIPTION_API_KEY"):
            client.transcribe(b"some audio data")

    def test_calls_remote_api(self):
        """Test successful remote API call."""
        RemoteTranscriptionClient._instance = None
        client = RemoteTranscriptionClient()
        client.api_key = "test-api-key"  # pragma: allowlist secret
        client.base_url = "https://api.openai.com/v1"
        client.model = "whisper-1"

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "Transcribed text from API"}
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", return_value=mock_client_instance):
            result = client.transcribe(b"audio bytes", format="webm")

        assert result == "Transcribed text from API"
        mock_client_instance.post.assert_called_once()
        call_kwargs = mock_client_instance.post.call_args
        assert "audio/transcriptions" in call_kwargs[0][0]

    def test_remote_api_strips_whitespace(self):
        """Test that the result text is stripped."""
        RemoteTranscriptionClient._instance = None
        client = RemoteTranscriptionClient()
        client.api_key = "test-api-key"  # pragma: allowlist secret
        client.base_url = "https://api.openai.com/v1"
        client.model = "whisper-1"

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "  Hello world  "}
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", return_value=mock_client_instance):
            result = client.transcribe(b"audio bytes")

        assert result == "Hello world"

    def test_reads_settings(self, settings):
        """Test that RemoteTranscriptionClient reads settings on init."""
        RemoteTranscriptionClient._instance = None
        settings.TRANSCRIPTION_API_KEY = "my-key"  # pragma: allowlist secret
        settings.TRANSCRIPTION_BASE_URL = "https://my-api.example.com/v1"
        settings.TRANSCRIPTION_MODEL = "my-model"

        client = RemoteTranscriptionClient()
        assert client.api_key == "my-key"  # pragma: allowlist secret
        assert client.base_url == "https://my-api.example.com/v1"
        assert client.model == "my-model"


class TestGetTranscriptionClient:
    def setup_method(self):
        _import_transcription_class.cache_clear()

    def test_returns_mock_by_default(self, settings):
        settings.TRANSCRIPTION_BACKEND = "apps.messages_app.transcription.MockTranscriptionClient"
        _import_transcription_class.cache_clear()
        client = get_transcription_client()
        assert isinstance(client, MockTranscriptionClient)

    def test_returns_configured_backend(self, settings):
        settings.TRANSCRIPTION_BACKEND = "apps.messages_app.transcription.MockTranscriptionClient"
        _import_transcription_class.cache_clear()
        client = get_transcription_client()
        assert isinstance(client, MockTranscriptionClient)

    def test_returns_remote_client_when_configured(self, settings):
        RemoteTranscriptionClient._instance = None
        settings.TRANSCRIPTION_BACKEND = "apps.messages_app.transcription.RemoteTranscriptionClient"
        _import_transcription_class.cache_clear()
        client = get_transcription_client()
        assert isinstance(client, RemoteTranscriptionClient)
        # cleanup singleton
        RemoteTranscriptionClient._instance = None
