"""Tests for health data sync API endpoint.

Covers:
  - POST /api/v1/health/sync/ — batch ingest from HealthKit / Health Connect
  - Dedup via unique constraint (skip duplicates silently)
  - Validation (source, concept_id, batch size)
  - Pipeline integration (batch processing queued)
"""

import json
from unittest.mock import patch

import pytest
from django.conf import settings as django_settings
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client

from apps.agents.tests.factories import PatientFactory
from apps.clinical.constants import CONCEPT_HEART_RATE, CONCEPT_SYSTOLIC_BP
from apps.clinical.models import ClinicalObservation


def _auth_client(patient):
    """Return a client with an authenticated patient session (no template render)."""
    session = SessionStore()
    session["authenticated"] = True
    session["patient_id"] = patient.id
    session.create()

    client = Client()
    client.cookies[django_settings.SESSION_COOKIE_NAME] = session.session_key
    return client


def _make_observation(concept_id=CONCEPT_HEART_RATE, value=72.0, **kwargs):
    obs = {
        "concept_id": concept_id,
        "value_numeric": value,
        "unit": "bpm",
        "observed_at": "2026-04-03T10:00:00+00:00",
        "source_device": "Apple Watch",
    }
    obs.update(kwargs)
    return obs


@pytest.mark.django_db
class TestHealthSyncAPI:
    """POST /api/v1/health/sync/"""

    @patch("apps.clinical.api._queue_batch_processing")
    def test_sync_single_observation(self, mock_queue):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/health/sync/",
            data=json.dumps(
                {
                    "source": "healthkit",
                    "observations": [_make_observation()],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["received"] == 1
        assert data["processed"] == 1
        assert data["skipped"] == 0
        assert data["errors"] == []

        # Verify in DB
        obs = ClinicalObservation.objects.filter(patient=patient, source="healthkit")
        assert obs.count() == 1
        assert obs.first().concept_id == CONCEPT_HEART_RATE

        # Verify batch processing was queued
        mock_queue.assert_called_once()

    @patch("apps.clinical.api._queue_batch_processing")
    def test_sync_multiple_observations(self, mock_queue):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/health/sync/",
            data=json.dumps(
                {
                    "source": "healthkit",
                    "observations": [
                        _make_observation(concept_id=CONCEPT_HEART_RATE, value=72.0),
                        _make_observation(
                            concept_id=CONCEPT_SYSTOLIC_BP,
                            value=120.0,
                            unit="mmHg",
                            observed_at="2026-04-03T10:01:00+00:00",
                        ),
                    ],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["received"] == 2
        assert data["processed"] == 2

    def test_sync_requires_auth(self):
        client = Client()
        response = client.post(
            "/api/v1/health/sync/",
            data=json.dumps(
                {
                    "source": "healthkit",
                    "observations": [_make_observation()],
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_sync_invalid_source(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/health/sync/",
            data=json.dumps(
                {
                    "source": "fitbit",
                    "observations": [_make_observation()],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_sync_exceeds_batch_limit(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/health/sync/",
            data=json.dumps(
                {
                    "source": "healthkit",
                    "observations": [_make_observation()] * 501,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400

    @patch("apps.clinical.api._queue_batch_processing")
    def test_sync_invalid_concept_id(self, mock_queue):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/health/sync/",
            data=json.dumps(
                {
                    "source": "healthkit",
                    "observations": [_make_observation(concept_id=9999999)],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 0
        assert data["skipped"] == 1
        assert len(data["errors"]) == 1
        assert "Invalid concept_id" in data["errors"][0]

    def test_sync_empty_observations(self):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/health/sync/",
            data=json.dumps(
                {
                    "source": "healthkit",
                    "observations": [],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["received"] == 0
        assert data["processed"] == 0

    @patch("apps.clinical.api._queue_batch_processing")
    def test_sync_dedup_skips_duplicates(self, mock_queue):
        """Duplicate observations (same patient/concept/time/source) are skipped."""
        patient = PatientFactory()

        obs = _make_observation()

        # First sync
        client1 = _auth_client(patient)
        response1 = client1.post(
            "/api/v1/health/sync/",
            data=json.dumps({"source": "healthkit", "observations": [obs]}),
            content_type="application/json",
        )
        assert response1.json()["processed"] == 1

        # Second sync with same data — should be skipped (fresh session)
        client2 = _auth_client(patient)
        response2 = client2.post(
            "/api/v1/health/sync/",
            data=json.dumps({"source": "healthkit", "observations": [obs]}),
            content_type="application/json",
        )
        data2 = response2.json()
        assert data2["skipped"] == 1
        assert data2["processed"] == 0

        # Only one record in DB
        assert ClinicalObservation.objects.filter(patient=patient, source="healthkit").count() == 1

    @patch("apps.clinical.api._queue_batch_processing")
    def test_sync_invalid_datetime(self, mock_queue):
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/health/sync/",
            data=json.dumps(
                {
                    "source": "healthkit",
                    "observations": [
                        _make_observation(observed_at="not-a-date"),
                    ],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["skipped"] == 1
        assert "Invalid observed_at" in data["errors"][0]

    @patch("apps.clinical.api._queue_batch_processing")
    def test_sync_health_connect_source(self, mock_queue):
        """Health Connect (Android) source is accepted."""
        patient = PatientFactory()
        client = _auth_client(patient)

        response = client.post(
            "/api/v1/health/sync/",
            data=json.dumps(
                {
                    "source": "health_connect",
                    "observations": [_make_observation()],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 1

        obs = ClinicalObservation.objects.get(patient=patient)
        assert obs.source == "health_connect"
