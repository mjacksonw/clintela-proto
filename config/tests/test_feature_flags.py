"""Tests for feature flag settings.

All ENABLE_* flags must use env.bool() so that '0', 'false', 'False'
are correctly parsed as False (not as a truthy string).
"""

import pytest
from django.conf import settings


class TestFeatureFlagsAreBooleans:
    """Every ENABLE_* setting must be a real Python bool, not a string."""

    @pytest.mark.parametrize(
        "flag",
        [
            "ENABLE_WEBSOCKETS",
            "ENABLE_CELERY",
            "ENABLE_SMS",
            "ENABLE_VOICE",
            "ENABLE_RAG",
            "ENABLE_CLINICAL_DATA",
        ],
    )
    def test_feature_flag_is_bool(self, flag):
        """ENABLE_* flags must be bool, never str (django-environ gotcha)."""
        value = getattr(settings, flag)
        assert isinstance(value, bool), (
            f"settings.{flag} is {type(value).__name__} ({value!r}), expected bool — use env.bool() in settings"
        )
