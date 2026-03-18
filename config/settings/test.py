"""
Test settings for Clintela project.
"""

from .base import *  # noqa: F401, F403

# =============================================================================
# TEST-SPECIFIC SETTINGS
# =============================================================================

# Use test database with environment overrides
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "clintela_test"),
        "USER": os.environ.get("POSTGRES_USER", "clintela"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "clintela"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5434"),
    }
}

# Use faster password hasher for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable migrations for faster tests
# class DisableMigrations:
#     def __contains__(self, item):
#         return True

#     def __getitem__(self, item):
#         return None

# MIGRATION_MODULES = DisableMigrations()

# =============================================================================
# CACHING - Use dummy cache in tests
# =============================================================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# =============================================================================
# EMAIL - Use console backend in tests
# =============================================================================
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# =============================================================================
# LOGGING - Reduce noise in tests
# =============================================================================
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "WARNING"  # noqa: F405

# =============================================================================
# SECURITY - Disable in tests
# =============================================================================
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# =============================================================================
# FEATURE FLAGS - Disable external services in tests
# =============================================================================
ENABLE_WEBSOCKETS = False
ENABLE_CELERY = False
ENABLE_SMS = False
ENABLE_VOICE = False

# Mock external API keys for tests
TWILIO_ACCOUNT_SID = "test_account_sid"
TWILIO_AUTH_TOKEN = "test_auth_token"
TWILIO_PHONE_NUMBER = "+15555555555"

OLLAMA_API_KEY = "test_ollama_key"
OLLAMA_BASE_URL = "https://test.ollama.com/v1"

# =============================================================================
# PASSWORD VALIDATION - Simplified for tests
# =============================================================================
AUTH_PASSWORD_VALIDATORS = []
