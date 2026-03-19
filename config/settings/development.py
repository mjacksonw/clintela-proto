"""
Development settings for Clintela project.
"""

from .base import *  # noqa: F401, F403

# =============================================================================
# DEVELOPMENT-SPECIFIC SETTINGS
# =============================================================================

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# Disable secure cookies in development
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# =============================================================================
# DEBUG TOOLS
# =============================================================================
INSTALLED_APPS += [  # noqa: F405
    "debug_toolbar",
]

MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405

INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
    "0.0.0.0",  # noqa: S104  # nosec B104 - Required for Docker internal
    "10.0.2.2",  # Docker internal
]

# Debug Toolbar configuration
DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: True,
    "SHOW_COLLAPSED": True,
    "DISABLE_PANELS": {
        "debug_toolbar.panels.redirects.RedirectsPanel",
    },
}

# =============================================================================
# DATABASE
# =============================================================================
# Use console email backend in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# =============================================================================
# LOGGING
# =============================================================================
# INFO level for development (less noisy than DEBUG)
LOGGING["loggers"]["django"]["level"] = "INFO"  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "INFO"  # noqa: F405

# =============================================================================
# CACHING - Use dummy cache in development
# =============================================================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}
