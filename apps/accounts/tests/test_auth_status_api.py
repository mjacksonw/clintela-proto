"""Tests for auth status API endpoint.

Covers:
  - GET /api/v1/auth/status/ — session check for mobile AuthBridge
  - Unauthenticated returns authenticated=false
  - Authenticated returns patient_id, preferred_name, expires_at
"""

import pytest
from django.conf import settings as django_settings
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client

from apps.agents.tests.factories import PatientFactory


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
class TestAuthStatusAPI:
    """GET /api/v1/auth/status/"""

    def test_unauthenticated_returns_false(self):
        client = Client()
        response = client.get("/api/v1/auth/status/")

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["patient_id"] is None

    def test_authenticated_returns_patient_info(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.get("/api/v1/auth/status/")

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["patient_id"] == str(patient.id)

    def test_authenticated_returns_preferred_name(self):
        patient = PatientFactory()
        patient.user.first_name = "Jordan"
        patient.user.save()

        client = _auth_client(patient)
        response = client.get("/api/v1/auth/status/")

        data = response.json()
        assert data["preferred_name"] == "Jordan"

    def test_authenticated_returns_expires_at(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.get("/api/v1/auth/status/")

        data = response.json()
        assert data["expires_at"] is not None

    def test_invalid_session_returns_false(self):
        """Session with authenticated=True but no patient_id."""
        session = SessionStore()
        session["authenticated"] = True
        # No patient_id
        session.create()

        client = Client()
        client.cookies[django_settings.SESSION_COOKIE_NAME] = session.session_key

        response = client.get("/api/v1/auth/status/")

        data = response.json()
        assert data["authenticated"] is False
