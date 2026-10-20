"""
ClinicFlow Django settings.

All secrets and environment-specific values are loaded from process env / `.env`
via django-environ (FR-CFG-1 .. FR-CFG-8, C-4, C-5).
"""

from __future__ import annotations

from pathlib import Path

import environ, os

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    SMS_BACKEND=(str, "mock"),
    REMINDER_LEAD_HOURS=(int, 24),
    SESSION_COOKIE_AGE=(int, 1800),
    REDIS_URL=(str, "redis://localhost:6379/0"),
)

# Local development: load `.env` if present. Missing file is not an error so
# container / CI environments can inject variables directly.
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# ---------------------------------------------------------------------------
# Core / secrets firewall (FR-CFG-2, FR-CFG-5)
# ---------------------------------------------------------------------------

# Fail-fast when SECRET_KEY is unset — no insecure default.
SECRET_KEY: str = env("SECRET_KEY")

DEBUG: bool = env.bool("DEBUG")  # defaults to False when unset (FR-CFG-6)

ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS")
if not DEBUG and not ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS must be set when DEBUG is False.")

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS: list[str] = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "clinics",
    "patients",
    "appointments",
]

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "clinicflow.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / 'templates'],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "clinicflow.context_processors.role_context_processor",
            ],
        },
    },
]

WSGI_APPLICATION = "clinicflow.wsgi.application"
ASGI_APPLICATION = "clinicflow.asgi.application"

# ---------------------------------------------------------------------------
# Database — interchangeable SQLite / PostgreSQL via DATABASE_URL (C-4, FR-CFG-8)
# ---------------------------------------------------------------------------


def _build_default_database() -> dict:
    """
    Select the engine from DATABASE_URL:

    * unset or ``sqlite:///``  -> SQLite (prototype default)
    * ``postgres://`` / ``postgresql://`` -> PostgreSQL
    """
    raw_url: str = env.str("DATABASE_URL", default="")
    if not raw_url:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }

    config = env.db("DATABASE_URL")
    if raw_url.startswith(("postgres://", "postgresql://")):
        config["ENGINE"] = "django.db.backends.postgresql"
        config.setdefault("CONN_MAX_AGE", 60)
        options = config.setdefault("OPTIONS", {})
        options.setdefault("connect_timeout", 10)
    elif raw_url.startswith("sqlite"):
        config["ENGINE"] = "django.db.backends.sqlite3"
    else:
        raise ValueError(
            "DATABASE_URL must be unset, start with sqlite:///, "
            "or start with postgres:// / postgresql://."
        )
    return config


DATABASES = {"default": _build_default_database()}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Auth / sessions (FR-AUTH-4, FR-AUTH-6, NFR-SEC-4)
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# 30 minutes of inactivity by default (FR-AUTH-6); overridable via env.
SESSION_COOKIE_AGE: int = env.int("SESSION_COOKIE_AGE")
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# ---------------------------------------------------------------------------
# Internationalization (C-10)
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

# ---------------------------------------------------------------------------
# SMS / Twilio (FR-SMS-12, FR-CFG-2, FR-CFG-5)
# ---------------------------------------------------------------------------

SMS_BACKEND: str = env.str("SMS_BACKEND").lower()
if SMS_BACKEND not in {"mock", "twilio"}:
    raise ValueError('SMS_BACKEND must be "mock" or "twilio".')

TWILIO_ACCOUNT_SID: str = env.str("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN: str = env.str("TWILIO_AUTH_TOKEN", default="")
TWILIO_FROM_NUMBER: str = env.str("TWILIO_FROM_NUMBER", default="")

if SMS_BACKEND == "twilio":
    missing = [
        name
        for name, value in (
            ("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT_SID),
            ("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN),
            ("TWILIO_FROM_NUMBER", TWILIO_FROM_NUMBER),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "SMS_BACKEND=twilio requires: " + ", ".join(missing)
        )

REMINDER_LEAD_HOURS: int = env.int("REMINDER_LEAD_HOURS")

# ---------------------------------------------------------------------------
# Celery / Redis broker (C-2, FR-SMS-14, SI-2, SI-5)
# ---------------------------------------------------------------------------

REDIS_URL: str = env.str("REDIS_URL")

CELERY_BROKER_URL: str = REDIS_URL
CELERY_RESULT_BACKEND: str = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Fallback in-process schedule used when Beat is started without DB entries.
# Period is 300 seconds (FR-SMS-2, SI-5).
CELERY_BEAT_SCHEDULE = {
    "scan-and-queue-reminders": {
        "task": "appointments.tasks.scan_and_queue_reminders",
        "schedule": 300.0,
    },
}

# ---------------------------------------------------------------------------
# HTTP security headers (CI-1, CI-7) — enabled outside DEBUG
# ---------------------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Restrictive CSP compatible with Bootstrap 5 CDN + Django admin.
SECURE_CSP = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "https://cdn.jsdelivr.net"],
    "style-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
    "img-src": ["'self'", "data:"],
    "font-src": ["'self'", "https://cdn.jsdelivr.net"],
    "connect-src": ["'self'"],
    "frame-ancestors": ["'none'"],
}

# ---------------------------------------------------------------------------
# Logging — stdout (container-friendly). Never log secret values (FR-CFG-7).
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "celery": {"handlers": ["console"], "level": "INFO"},
        "clinicflow.sms.mock": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "appointments.tasks": {"handlers": ["console"], "level": "INFO"},
    },
}

# Console email backend — v1.0 does not send email (CI-6).
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}


# Authentication Core Redirects
LOGIN_REDIRECT_URL = '/'

LOGOUT_REDIRECT_URL = '/login/'
