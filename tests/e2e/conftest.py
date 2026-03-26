"""Conftest for Playwright E2E tests."""

import os

import pytest
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from playwright.sync_api import Page

from apps.accounts.models import User
from apps.clinicians.models import Clinician
from apps.patients.models import Hospital, Patient

# Allow Django ORM in async context (Playwright uses its own event loop)
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture()
def test_patient(db):
    """Create a test patient for E2E tests."""
    hospital = Hospital.objects.create(name="E2E Hospital", code="E2E01")
    user = User.objects.create_user(
        username="e2e_patient",
        password="testpass",  # noqa: S106  # pragma: allowlist secret
        first_name="Alex",
        last_name="Test",
    )
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-05-20",
        leaflet_code="E2ETEST",
        surgery_type="Hip Replacement",
        status="green",
    )
    return patient


@pytest.fixture()
def authenticated_page(page: Page, live_server, test_patient):
    """Return a Playwright page with an authenticated patient session.

    Creates a Django session directly in the DB and sets the cookie via Playwright.
    """
    # Create a session directly in the DB (shared between test and live_server)
    session = SessionStore()
    session["patient_id"] = str(test_patient.id)
    session["authenticated"] = True
    session.create()

    # Navigate to the live server first to set domain context
    page.goto(live_server.url)

    # Set the session cookie
    page.context.add_cookies(
        [
            {
                "name": "sessionid",
                "value": session.session_key,
                "domain": "localhost",
                "path": "/",
            }
        ]
    )

    return page


@pytest.fixture()
def test_clinician(test_patient):
    """Create a test clinician linked to the same hospital as test_patient."""
    user = User.objects.create_user(
        username="e2e_clinician",
        password="testpass",  # noqa: S106  # pragma: allowlist secret
        first_name="Dr",
        last_name="E2E",
        role="clinician",
    )
    clinician = Clinician.objects.create(
        user=user,
        role="physician",
        is_active=True,
    )
    clinician.hospitals.add(test_patient.hospital)
    return clinician


@pytest.fixture()
def authenticated_clinician_page(page: Page, live_server, test_clinician):
    """Return a Playwright page with an authenticated clinician session."""
    session = SessionStore()
    session[SESSION_KEY] = str(test_clinician.user.pk)
    session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    session[HASH_SESSION_KEY] = test_clinician.user.get_session_auth_hash()
    session.create()

    page.goto(live_server.url)
    page.context.add_cookies(
        [
            {
                "name": "sessionid",
                "value": session.session_key,
                "domain": "localhost",
                "path": "/",
            }
        ]
    )
    return page
