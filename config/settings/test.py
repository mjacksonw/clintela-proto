"""
Test settings for Clintela project.
"""

# =============================================================================
# TEST-SPECIFIC SETTINGS
# =============================================================================
# Use test database with environment overrides
import os

from .base import *  # noqa: F401, F403

# Support DATABASE_URL env var (used by GitHub Actions) or individual POSTGRES_* vars
if "DATABASE_URL" in os.environ:
    # Use base.py's env instance which is already imported via *
    DATABASES = {"default": env.db()}  # noqa: F405
else:
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
# CACHING - Use local memory cache for rate limiting tests
# =============================================================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
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

# Mock external API keys for tests (nosec: test-only credentials)
TWILIO_ACCOUNT_SID = "test_account_sid"  # nosec B105
TWILIO_AUTH_TOKEN = "test_auth_token"  # nosec B105
TWILIO_PHONE_NUMBER = "+15555555555"

OLLAMA_API_KEY = "test_ollama_key"
OLLAMA_BASE_URL = "https://test.ollama.com/v1"

# =============================================================================
# PASSWORD VALIDATION - Simplified for tests
# =============================================================================
AUTH_PASSWORD_VALIDATORS = []
