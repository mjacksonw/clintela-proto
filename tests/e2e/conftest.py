"""Conftest for Playwright E2E tests."""

import os

import pytest
from django.contrib.sessions.backends.db import SessionStore
from playwright.sync_api import Page

from apps.accounts.models import User
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
