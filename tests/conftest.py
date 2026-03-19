"""
Pytest configuration for Clintela.

For more information, see:
https://pytest-django.readthedocs.io/en/latest/
"""

from unittest.mock import patch

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
def disable_rate_limiting():
    """Disable rate limiting for all tests to avoid 403 errors."""
    from functools import wraps

    from django_ratelimit.decorators import ratelimit

    # Store the original ratelimit decorator
    original_ratelimit = ratelimit

    # Create a no-op version that just passes through
    def noop_ratelimit(*args, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*f_args, **f_kwargs):
                return func(*f_args, **f_kwargs)

            return wrapper

        return decorator

    # Patch the ratelimit decorator
    with patch("apps.accounts.views.ratelimit", noop_ratelimit):
        with patch("django_ratelimit.decorators.ratelimit", noop_ratelimit):
            yield


@pytest.fixture
def disable_rate_limiting_fixture():
    """Disable rate limiting for tests that need it."""
    from functools import wraps

    def noop_ratelimit(*args, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*f_args, **f_kwargs):
                return func(*f_args, **f_kwargs)

            return wrapper

        return decorator

    with patch("apps.accounts.views.ratelimit", noop_ratelimit):
        with patch("django_ratelimit.decorators.ratelimit", noop_ratelimit):
            yield
