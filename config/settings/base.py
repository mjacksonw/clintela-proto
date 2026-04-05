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
    PROTECTED=(bool, False),
    PROTECTED_GATE_PATH=(str, "letmein"),
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
PROTECTED = env("PROTECTED")
PROTECTED_GATE_PATH = env("PROTECTED_GATE_PATH")
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
    "corsheaders",
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
    "apps.surveys",
    "apps.administrators",
    "apps.clinical",
]

# Daphne must be first so its ASGI-capable runserver replaces Django's WSGI one.
INSTALLED_APPS = ["daphne"] + DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# =============================================================================
# MIDDLEWARE
# =============================================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.accounts.middleware.ProtectedEnvironmentMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "apps.patients.middleware.PatientLanguageMiddleware",
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
                "apps.clinical.context_processors.clinical_data_flags",
                "apps.agents.context_processors.support_group_flags",
                "apps.accounts.context_processors.demo_bar_context",
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
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ("en", "English"),
    ("es", "Spanish"),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

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
# CORS (django-cors-headers)
# =============================================================================
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
)
CORS_ALLOW_CREDENTIALS = True

# =============================================================================
# CONTENT SECURITY POLICY (django-csp)
# =============================================================================
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "api.fontshare.com", "cdn.jsdelivr.net")
CSP_FONT_SRC = ("'self'", "api.fontshare.com", "cdn.fontshare.com")
CSP_IMG_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = ("'self'", "ws:", "wss:")
CSP_FRAME_ANCESTORS = ("'none'",)

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

# LangSmith (opt-in tracing — set env vars to enable)
# LangSmith checks os.environ for the literal string "true" (lowercase),
# so we normalize the value after django-environ reads it.
LANGSMITH_TRACING = env.bool("LANGSMITH_TRACING", default=False)
LANGSMITH_API_KEY = env("LANGSMITH_API_KEY", default=None)
LANGSMITH_PROJECT = env("LANGSMITH_PROJECT", default="clintela")

if LANGSMITH_TRACING:
    import os

    os.environ["LANGSMITH_TRACING"] = "true"

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
    "create-survey-instances": {
        "task": "apps.surveys.tasks.create_survey_instances",
        "schedule": 86400,  # daily (task self-schedules at 6:03 AM)
    },
    "expire-survey-instances": {
        "task": "apps.surveys.tasks.expire_survey_instances",
        "schedule": 1800,  # every 30 minutes
    },
    "compute-daily-metrics": {
        "task": "apps.analytics.tasks.compute_daily_metrics",
        "schedule": crontab(hour=2, minute=7),  # 2:07 AM daily
    },
    "send-appointment-reminders": {
        "task": "apps.clinicians.tasks.send_appointment_reminders",
        "schedule": 900,  # every 15 minutes
    },
    "expire-appointment-requests": {
        "task": "apps.clinicians.tasks.expire_appointment_requests",
        "schedule": crontab(hour=3, minute=17),  # daily at 3:17 AM
    },
    "notify-upcoming-appointments": {
        "task": "apps.clinicians.tasks.notify_upcoming_appointments",
        "schedule": crontab(hour=8, minute=3),  # daily at 8:03 AM
    },
}

# =============================================================================
# FEATURE FLAGS
# =============================================================================
ENABLE_WEBSOCKETS = env.bool("ENABLE_WEBSOCKETS", default=False)
ENABLE_CELERY = env.bool("ENABLE_CELERY", default=False)
ENABLE_SMS = env.bool("ENABLE_SMS", default=False)
ENABLE_VOICE = env.bool("ENABLE_VOICE", default=False)
ENABLE_RAG = env.bool("ENABLE_RAG", default=False)
ENABLE_CLINICAL_DATA = env.bool("ENABLE_CLINICAL_DATA", default=False)

# =============================================================================
# EMBEDDING / RAG
# =============================================================================
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="qwen3-embedding:4b")
EMBEDDING_DIMENSIONS = env.int("EMBEDDING_DIMENSIONS", default=2000)
EMBEDDING_BASE_URL = env("EMBEDDING_BASE_URL", default="http://localhost:11434")
EMBEDDING_QUERY_INSTRUCTION = env(
    "EMBEDDING_QUERY_INSTRUCTION",
    default="Retrieve clinical cardiology guidelines relevant to this patient question: ",
)

RAG_TOP_K = env.int("RAG_TOP_K", default=5)
RAG_SIMILARITY_THRESHOLD = env.float("RAG_SIMILARITY_THRESHOLD", default=0.7)
RAG_VECTOR_WEIGHT = env.float("RAG_VECTOR_WEIGHT", default=0.7)
RAG_TEXT_WEIGHT = env.float("RAG_TEXT_WEIGHT", default=0.3)
