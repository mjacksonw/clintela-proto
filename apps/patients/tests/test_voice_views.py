"""Tests for voice input views."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.patients.models import Hospital, Patient


@pytest.mark.django_db
class TestVoiceSendView:
    """Test patient_voice_send_view."""

    def setup_method(self):
        self.user = User.objects.create_user(username="voiceuser", password="testpass")
        self.hospital = Hospital.objects.create(name="Voice Hospital", code="VOICE01")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1985-06-15",
            leaflet_code="VOICE99",
            surgery_type="Knee Replacement",
        )

    def _get_authenticated_client(self):
        client = Client()
        session = client.session
        session["patient_id"] = str(self.patient.id)
        session["authenticated"] = True
        session.save()
        return client

    def _make_audio_file(self, name="recording.webm", size=1024):
        return SimpleUploadedFile(
            name,
            b"\x00" * size,
            content_type="audio/webm",
        )

    def test_unauthenticated_returns_403(self):
        client = Client()
        audio = self._make_audio_file()
        response = client.post(reverse("patients:voice_send"), {"audio": audio})
        assert response.status_code == 403

    def test_no_audio_file_returns_400(self):
        client = self._get_authenticated_client()
        response = client.post(reverse("patients:voice_send"))
        assert response.status_code == 400

    def test_oversized_file_returns_413(self):
        client = self._get_authenticated_client()
        max_bytes = (getattr(settings, "VOICE_MEMO_MAX_SIZE_MB", 10) * 1024 * 1024) + 1
        audio = self._make_audio_file(size=max_bytes)
        response = client.post(reverse("patients:voice_send"), {"audio": audio})
        assert response.status_code == 413

    def test_invalid_content_type_returns_415(self):
        client = self._get_authenticated_client()
        file = SimpleUploadedFile("doc.pdf", b"fake", content_type="application/pdf")
        response = client.post(reverse("patients:voice_send"), {"audio": file})
        assert response.status_code == 415

    @patch("apps.agents.workflow.get_workflow")
    @patch("apps.messages_app.transcription.get_transcription_client")
    def test_valid_audio_returns_html(self, mock_get_client, mock_get_workflow):
        from apps.messages_app.transcription import MockTranscriptionClient

        mock_client = MockTranscriptionClient()
        mock_get_client.return_value = mock_client

        mock_workflow = mock_get_workflow.return_value
        mock_workflow.process_message = AsyncMock(
            return_value={
                "response": "I understand your concern.",
                "agent_type": "care_coordinator",
                "escalate": False,
                "escalation_reason": "",
                "metadata": {"confidence": 0.9},
            }
        )

        client = self._get_authenticated_client()
        audio = self._make_audio_file()
        response = client.post(reverse("patients:voice_send"), {"audio": audio})

        assert response.status_code == 200
        content = response.content.decode()
        assert "I understand your concern." in content

    @patch("apps.agents.workflow.get_workflow")
    @patch("apps.messages_app.transcription.get_transcription_client")
    def test_saves_audio_file_to_disk(self, mock_get_client, mock_get_workflow):
        from apps.messages_app.transcription import MockTranscriptionClient

        mock_get_client.return_value = MockTranscriptionClient()
        mock_workflow = mock_get_workflow.return_value
        mock_workflow.process_message = AsyncMock(
            return_value={
                "response": "OK",
                "agent_type": "care_coordinator",
                "escalate": False,
                "escalation_reason": "",
                "metadata": {},
            }
        )

        client = self._get_authenticated_client()
        audio = self._make_audio_file()
        client.post(reverse("patients:voice_send"), {"audio": audio})

        voice_dir = Path(settings.MEDIA_ROOT) / "voice_memos" / str(self.patient.id)
        saved_files = list(voice_dir.glob("*.webm"))
        assert len(saved_files) >= 1

    def test_get_method_returns_405(self):
        client = self._get_authenticated_client()
        response = client.get(reverse("patients:voice_send"))
        assert response.status_code == 405


@pytest.mark.django_db
class TestVoiceFileView:
    """Test patient_voice_file_view."""

    def setup_method(self):
        self.user = User.objects.create_user(username="voicefile", password="testpass")
        self.hospital = Hospital.objects.create(name="VF Hospital", code="VF01")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1990-01-01",
            leaflet_code="VF99",
            surgery_type="Hip Replacement",
        )

    def _get_authenticated_client(self):
        client = Client()
        session = client.session
        session["patient_id"] = str(self.patient.id)
        session["authenticated"] = True
        session.save()
        return client

    def test_unauthenticated_returns_403(self):
        client = Client()
        file_id = uuid.uuid4()
        response = client.get(reverse("patients:voice_file", kwargs={"file_id": file_id}))
        assert response.status_code == 403

    def test_nonexistent_file_returns_404(self):
        client = self._get_authenticated_client()
        file_id = uuid.uuid4()
        response = client.get(reverse("patients:voice_file", kwargs={"file_id": file_id}))
        assert response.status_code == 404

    def test_existing_file_returns_audio(self):
        client = self._get_authenticated_client()
        file_id = uuid.uuid4()

        # Create the file on disk
        voice_dir = Path(settings.MEDIA_ROOT) / "voice_memos" / str(self.patient.id)
        voice_dir.mkdir(parents=True, exist_ok=True)
        file_path = voice_dir / f"{file_id}.webm"
        file_path.write_bytes(b"\x00" * 100)

        response = client.get(reverse("patients:voice_file", kwargs={"file_id": file_id}))
        assert response.status_code == 200
        assert response["Content-Type"] == "audio/webm"
