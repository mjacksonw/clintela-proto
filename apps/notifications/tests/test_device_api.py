"""Tests for device registration API endpoints.

Covers:
  - POST /api/v1/devices/register/ — idempotent push token registration
  - DELETE /api/v1/devices/{token}/ — IDOR-safe token deactivation
  - Auth enforcement on both endpoints
  - Validation (platform, token length)
"""

import json

import pytest
from django.conf import settings as django_settings
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client

from apps.agents.tests.factories import PatientFactory
from apps.notifications.models import DeviceToken
from apps.notifications.tests.factories import DeviceTokenFactory


def _auth_client(patient):
    """Return a client with an authenticated patient session (no template render)."""
    session = SessionStore()
    session["authenticated"] = True
    session["patient_id"] = patient.id
    session.create()

    client = Client()
    client.cookies[django_settings.SESSION_COOKIE_NAME] = session.session_key
    return client


@pytest.mark.django_db
class TestDeviceRegisterAPI:
    """POST /api/v1/devices/register/"""

    def test_register_new_device(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/devices/register/",
            data=json.dumps(
                {
                    "token": "fcm_new_device_token_001",
                    "platform": "ios",
                    "device_name": "iPhone 15 Pro",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "fcm_new_device_token_001"
        assert data["platform"] == "ios"
        assert data["is_active"] is True
        assert data["created"] is True

        # Verify in DB
        assert DeviceToken.objects.filter(token="fcm_new_device_token_001").exists()

    def test_register_reactivates_existing(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        # Create an inactive token
        DeviceToken.objects.create(
            patient=patient,
            token="reactivate_token",
            platform="ios",
            is_active=False,
        )

        response = client.post(
            "/api/v1/devices/register/",
            data=json.dumps(
                {
                    "token": "reactivate_token",
                    "platform": "ios",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True
        assert data["created"] is False

    def test_register_requires_auth(self):
        client = Client()
        response = client.post(
            "/api/v1/devices/register/",
            data=json.dumps(
                {
                    "token": "token",
                    "platform": "ios",
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_register_invalid_platform(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/devices/register/",
            data=json.dumps(
                {
                    "token": "some_token",
                    "platform": "windows",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_register_empty_token(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/devices/register/",
            data=json.dumps(
                {
                    "token": "",
                    "platform": "ios",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_register_token_too_long(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/devices/register/",
            data=json.dumps(
                {
                    "token": "x" * 256,
                    "platform": "ios",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestDeviceDeleteAPI:
    """DELETE /api/v1/devices/{token}/"""

    def test_delete_deactivates_token(self):
        patient = PatientFactory()
        device = DeviceTokenFactory(patient=patient, token="delete_me_token")
        client = _auth_client(patient)

        response = client.delete("/api/v1/devices/delete_me_token/")

        assert response.status_code == 200
        data = response.json()
        assert data["deactivated"] is True

        device.refresh_from_db()
        assert device.is_active is False
        assert device.deactivated_at is not None

    def test_delete_requires_auth(self):
        client = Client()
        response = client.delete("/api/v1/devices/some_token/")
        assert response.status_code == 401

    def test_delete_idor_prevention(self):
        """Patient A cannot deactivate Patient B's token."""
        patient_a = PatientFactory()
        patient_b = PatientFactory()
        DeviceTokenFactory(patient=patient_b, token="patient_b_token")

        client = _auth_client(patient_a)
        response = client.delete("/api/v1/devices/patient_b_token/")

        assert response.status_code == 404

    def test_delete_nonexistent_token(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.delete("/api/v1/devices/nonexistent_token/")

        assert response.status_code == 404

    def test_delete_already_inactive(self):
        """Deleting an already-inactive token returns 404."""
        patient = PatientFactory()
        DeviceTokenFactory(patient=patient, token="already_inactive", is_active=False)
        client = _auth_client(patient)

        response = client.delete("/api/v1/devices/already_inactive/")

        assert response.status_code == 404
