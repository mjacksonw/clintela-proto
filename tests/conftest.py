"""
Pytest configuration for Clintela.

For more information, see:
https://pytest-django.readthedocs.io/en/latest/
"""

import pytest


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Set up the database for the test session."""
    # Any database setup that should happen once per test session
    pass


@pytest.fixture
def client(client):
    """Provide a Django test client."""
    return client
