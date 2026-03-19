"""Test configuration for accounts views tests.

Patches ratelimit decorator to be a no-op for view tests.
This file is used for test_views.py by being in the same directory.
"""

import sys
from functools import wraps
from unittest.mock import MagicMock


def create_noop_ratelimit():
    """Create a no-op ratelimit decorator."""

    def ratelimit(*args, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*f_args, **f_kwargs):
                return func(*f_args, **f_kwargs)

            return wrapper

        return decorator

    return ratelimit


# Create mock django_ratelimit module with noop decorator
noop_ratelimit = create_noop_ratelimit()

# Create a mock decorators module
mock_decorators = MagicMock()
mock_decorators.ratelimit = noop_ratelimit

# Create mock django_ratelimit module
mock_django_ratelimit = MagicMock()
mock_django_ratelimit.decorators = mock_decorators

# Replace the module in sys.modules BEFORE any imports
sys.modules["django_ratelimit"] = mock_django_ratelimit
sys.modules["django_ratelimit.decorators"] = mock_decorators
