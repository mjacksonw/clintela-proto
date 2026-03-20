"""Tests for SMS webhook views."""

import pytest

from apps.messages_app.backends import LocMemSMSBackend


@pytest.mark.django_db
class TestTwilioInboundWebhook:
    def setup_method(self):
        LocMemSMSBackend.reset()

    @pytest.fixture(autouse=True)
    def _enable_debug(self, settings):
        settings.DEBUG = True

    def test_returns_twiml(self, client):
        response = client.post(
            "/sms/webhook/",
            {"From": "+15551234567", "Body": "Hello", "MessageSid": "SM123"},
        )

        assert response.status_code == 200
        assert "text/xml" in response["Content-Type"]
        assert "<Response>" in response.content.decode()

    def test_returns_200_on_error(self, client):
        """Always returns 200 to prevent Twilio retries."""
        response = client.post(
            "/sms/webhook/",
            {"From": "", "Body": ""},
        )
        assert response.status_code == 200

    def test_returns_200_on_missing_params(self, client):
        response = client.post("/sms/webhook/", {})
        assert response.status_code == 200

    def test_get_not_allowed(self, client):
        response = client.get("/sms/webhook/")
        assert response.status_code == 405


@pytest.mark.django_db
class TestTwilioStatusWebhook:
    @pytest.fixture(autouse=True)
    def _enable_debug(self, settings):
        settings.DEBUG = True

    def test_updates_delivery_status(self, client):
        from apps.notifications.tests.factories import (
            NotificationDeliveryFactory,
        )

        delivery = NotificationDeliveryFactory(channel="sms", status="sent", external_id="SM_TEST_123")

        response = client.post(
            "/sms/status/",
            {"MessageSid": "SM_TEST_123", "MessageStatus": "delivered"},
        )

        assert response.status_code == 200
        delivery.refresh_from_db()
        assert delivery.status == "delivered"
        assert delivery.delivered_at is not None

    def test_handles_failed_status(self, client):
        from apps.notifications.tests.factories import (
            NotificationDeliveryFactory,
        )

        delivery = NotificationDeliveryFactory(channel="sms", status="sent", external_id="SM_FAIL_123")

        response = client.post(
            "/sms/status/",
            {"MessageSid": "SM_FAIL_123", "MessageStatus": "failed"},
        )

        assert response.status_code == 200
        delivery.refresh_from_db()
        assert delivery.status == "failed"

    def test_ignores_unknown_sid(self, client):
        response = client.post(
            "/sms/status/",
            {"MessageSid": "SM_NONEXISTENT", "MessageStatus": "delivered"},
        )
        assert response.status_code == 200

    def test_get_not_allowed(self, client):
        response = client.get("/sms/status/")
        assert response.status_code == 405
