"""Test Django configuration."""

import pytest
from django.conf import settings


def test_settings_loaded():
    """Test that Django settings are properly configured."""
    assert settings.SECRET_KEY is not None
    assert "django.contrib.auth" in settings.INSTALLED_APPS


def test_database_configured():
    """Test that database is configured."""
    assert "default" in settings.DATABASES
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"


def test_auth_user_model():
    """Test custom user model is configured."""
    assert settings.AUTH_USER_MODEL == "accounts.User"
