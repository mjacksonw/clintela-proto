"""Tests for patient_chat_send_view."""

from unittest.mock import AsyncMock, patch

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.patients.models import Hospital, Patient


@pytest.mark.django_db
class TestChatSendView:
    """Test patient_chat_send_view."""

    def setup_method(self):
        """Set up test patient and authenticated session."""
        self.user = User.objects.create_user(username="chatuser", password="testpass")
        self.hospital = Hospital.objects.create(name="Chat Hospital", code="CHAT01")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1985-06-15",
            leaflet_code="CHAT99",
            surgery_type="Knee Replacement",
        )

    def _get_authenticated_client(self):
        client = Client()
        session = client.session
        session["patient_id"] = str(self.patient.id)
        session["authenticated"] = True
        session.save()
        return client

    def test_unauthenticated_returns_403(self):
        """Unauthenticated request returns 403."""
        client = Client()
        response = client.post(reverse("patients:chat_send"), {"message": "hello"})
        assert response.status_code == 403

    def test_empty_message_returns_400(self):
        """Empty message returns 400."""
        client = self._get_authenticated_client()
        response = client.post(reverse("patients:chat_send"), {"message": ""})
        assert response.status_code == 400

    def test_whitespace_message_returns_400(self):
        """Whitespace-only message returns 400."""
        client = self._get_authenticated_client()
        response = client.post(reverse("patients:chat_send"), {"message": "   "})
        assert response.status_code == 400

    def test_get_method_returns_405(self):
        """GET request returns 405 (require_POST decorator)."""
        client = self._get_authenticated_client()
        response = client.get(reverse("patients:chat_send"))
        assert response.status_code == 405

    @patch("apps.patients.views.get_workflow")
    def test_valid_message_returns_html_fragment(self, mock_get_workflow):
        """Valid message returns HTML fragment with message bubble."""
        mock_workflow = mock_get_workflow.return_value
        mock_workflow.process_message = AsyncMock(
            return_value={
                "response": "Recovery is going well!",
                "agent_type": "care_coordinator",
                "escalate": False,
                "escalation_reason": "",
                "metadata": {"confidence": 0.9},
            }
        )

        client = self._get_authenticated_client()
        response = client.post(
            reverse("patients:chat_send"),
            {"message": "How am I doing?"},
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Recovery is going well!" in content

    @patch("apps.patients.views.get_workflow")
    def test_escalation_sets_hx_trigger(self, mock_get_workflow):
        """Escalation response includes HX-Trigger header."""
        mock_workflow = mock_get_workflow.return_value
        mock_workflow.process_message = AsyncMock(
            return_value={
                "response": "I'm connecting you with a nurse right away.",
                "agent_type": "nurse_triage",
                "escalate": True,
                "escalation_reason": "Severe chest pain",
                "metadata": {"severity": "critical"},
            }
        )

        client = self._get_authenticated_client()
        response = client.post(
            reverse("patients:chat_send"),
            {"message": "I'm having severe chest pain"},
        )

        assert response.status_code == 200
        assert response.get("HX-Trigger") == "escalation"
