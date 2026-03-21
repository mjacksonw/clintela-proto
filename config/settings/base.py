"""
Django settings for Clintela project.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

from pathlib import Path

import environ

# =============================================================================
# PATHS
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_COOKIE_SECURE=(bool, True),
    SESSION_COOKIE_SECURE=(bool, True),
    SECURE_SSL_REDIRECT=(bool, True),
    SECURE_HSTS_SECONDS=(int, 31536000),
    SECURE_HSTS_INCLUDE_SUBDOMAINS=(bool, True),
    SECURE_HSTS_PRELOAD=(bool, True),
)

# Read .env file if it exists
environ.Env.read_env(BASE_DIR / ".env")

# =============================================================================
# CORE SETTINGS
# =============================================================================
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# =============================================================================
# APPLICATIONS
# =============================================================================
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "django_extensions",
    "ninja",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.patients",
    "apps.caregivers",
    "apps.clinicians",
    "apps.agents",
    "apps.messages_app",
    "apps.pathways",
    "apps.notifications",
    "apps.analytics",
    "apps.knowledge",
    "apps.administrators",
]

# Daphne must be first so its ASGI-capable runserver replaces Django's WSGI one.
INSTALLED_APPS = ["daphne"] + DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# =============================================================================
# MIDDLEWARE
# =============================================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# =============================================================================
# URLS
# =============================================================================
ROOT_URLCONF = "config.urls"

# =============================================================================
# TEMPLATES
# =============================================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# =============================================================================
# WSGI/ASGI
# =============================================================================
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# =============================================================================
# DATABASE
# =============================================================================
DATABASES = {
    "default": env.db(),
}

# =============================================================================
# PASSWORD VALIDATION
# =============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# =============================================================================
# AUTHENTICATION
# =============================================================================
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC FILES
# =============================================================================
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# =============================================================================
# MEDIA FILES
# =============================================================================
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# SECURITY
# =============================================================================
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE")
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE")

# Session configuration - 7-day rolling sessions
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60  # 7 days in seconds
SESSION_SAVE_EVERY_REQUEST = True  # Rolling window - extends on every request
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# django-ratelimit configuration
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"

SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS")
SECURE_HSTS_INCLUDE_SUBDOMAINS = env("SECURE_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = env("SECURE_HSTS_PRELOAD")

# =============================================================================
# LOGGING
# =============================================================================
LOG_DIR = BASE_DIR / env("LOG_DIR", default="logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_LEVEL = env("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "formatter": "verbose",
        },
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "django.request": {
            "handlers": ["file", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

# =============================================================================
# EMAIL
# =============================================================================
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

# =============================================================================
# CACHING (Redis)
# =============================================================================
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# =============================================================================
# CHANNELS (WebSockets)
# =============================================================================
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://localhost:6379/0")],
        },
    },
}

# =============================================================================
# THIRD-PARTY SETTINGS
# =============================================================================

# Twilio
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default=None)
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", default=None)
TWILIO_PHONE_NUMBER = env("TWILIO_PHONE_NUMBER", default=None)

# Ollama / LLM
OLLAMA_API_KEY = env("OLLAMA_API_KEY", default=None)
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", default="https://api.ollama.com/v1")
OLLAMA_MODEL = env("OLLAMA_MODEL", default="llama3.2")
OLLAMA_TIMEOUT = env.int("OLLAMA_TIMEOUT", default=90)
OLLAMA_MAX_RETRIES = env.int("OLLAMA_MAX_RETRIES", default=3)

# =============================================================================
# NOTIFICATION BACKENDS
# =============================================================================
NOTIFICATION_BACKENDS = {
    "in_app": "apps.notifications.backends.InAppBackend",
    "sms": "apps.notifications.backends.SMSBackend",
    "email": "apps.notifications.backends.EmailBackend",
}

# =============================================================================
# SMS
# =============================================================================
SMS_BACKEND = "apps.messages_app.backends.ConsoleSMSBackend"
SMS_RATE_LIMIT_PER_HOUR = env.int("SMS_RATE_LIMIT_PER_HOUR", default=10)

# =============================================================================
# VOICE
# =============================================================================
TRANSCRIPTION_BACKEND = "apps.messages_app.transcription.MockTranscriptionClient"
VOICE_MEMO_RETENTION_HOURS = env.int("VOICE_MEMO_RETENTION_HOURS", default=24)
VOICE_MEMO_MAX_SIZE_MB = env.int("VOICE_MEMO_MAX_SIZE_MB", default=10)
VOICE_MEMO_MAX_DURATION_SECONDS = env.int("VOICE_MEMO_MAX_DURATION_SECONDS", default=60)

# =============================================================================
# CELERY
# =============================================================================
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6380/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
from celery.schedules import crontab  # noqa: E402

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "send-scheduled-reminders": {
        "task": "apps.notifications.tasks.send_scheduled_reminders",
        "schedule": 300,  # every 5 minutes
    },
    "cleanup-voice-files": {
        "task": "apps.messages_app.tasks.cleanup_expired_voice_files",
        "schedule": 3600,  # every hour
    },
    "compute-daily-metrics": {
        "task": "apps.analytics.tasks.compute_daily_metrics",
        "schedule": crontab(hour=2, minute=7),  # 2:07 AM daily
    },
}

# =============================================================================
# FEATURE FLAGS
# =============================================================================
ENABLE_WEBSOCKETS = env("ENABLE_WEBSOCKETS", default=False)
ENABLE_CELERY = env("ENABLE_CELERY", default=False)
ENABLE_SMS = env("ENABLE_SMS", default=False)
ENABLE_VOICE = env("ENABLE_VOICE", default=False)
ENABLE_RAG = env("ENABLE_RAG", default=False)

# =============================================================================
# EMBEDDING / RAG
# =============================================================================
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="nomic-embed-text")
EMBEDDING_DIMENSIONS = env.int("EMBEDDING_DIMENSIONS", default=768)
EMBEDDING_BASE_URL = env("EMBEDDING_BASE_URL", default="http://localhost:11434")

RAG_TOP_K = env.int("RAG_TOP_K", default=5)
RAG_SIMILARITY_THRESHOLD = env.float("RAG_SIMILARITY_THRESHOLD", default=0.7)
RAG_VECTOR_WEIGHT = env.float("RAG_VECTOR_WEIGHT", default=0.7)
RAG_TEXT_WEIGHT = env.float("RAG_TEXT_WEIGHT", default=0.3)
