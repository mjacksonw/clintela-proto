"""Tests for transcription backends."""

from apps.messages_app.transcription import (
    MockTranscriptionClient,
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
