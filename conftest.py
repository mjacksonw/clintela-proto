"""
Pytest configuration for Clintela.

This conftest.py is placed at the project root to ensure fixtures are
available to all tests (both in tests/ and apps/).

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


@pytest.fixture(autouse=True)
def disable_rate_limiting(request, settings):
    """Disable rate limiting for view tests to avoid 403 errors.

    Rate limiting tests are identified by their nodeid and need rate limiting enabled.
    All other tests have rate limiting disabled via RATELIMIT_ENABLE=False.

    This setting is checked at runtime in django_ratelimit.core.get_usage(),
    so using override_settings works correctly even though the decorator
    is applied at import time.

    IMPORTANT: Cache is cleared before ALL tests to ensure isolation when running
    with pytest-xdist, since each worker has its own LocMemCache instance that
    persists across tests within that worker.
    """
    from django.core.cache import cache

    # Always clear cache before each test for isolation
    cache.clear()

    test_nodeid = request.node.nodeid

    # Rate limiting tests need the real ratelimit functionality
    if "test_rate_limiting" in test_nodeid:
        yield
        # Clear after rate limiting tests for good measure
        cache.clear()
        return

    # For all other tests, disable rate limiting entirely via pytest-django's settings fixture
    settings.RATELIMIT_ENABLE = False
    yield


@pytest.fixture
def clear_rate_limit_cache():
    """Clear the rate limit cache for test isolation.

    Use this fixture in rate limiting tests that need a fresh cache state.
    """
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
