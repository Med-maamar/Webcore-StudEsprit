import os
from pathlib import Path
from dotenv import load_dotenv
import logging.config


# Load environment variables from .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
DEBUG = os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"}
# For local development, avoid hardcoding HTTPS origins to prevent HTTPS-only behavior.
# Uncomment the production origin below when deploying.
# CSRF_TRUSTED_ORIGINS = ['https://webcore-studesprit.onrender.com']
# CSRF Trusted Origins — FIXED FOR PRODUCTION
CSRF_TRUSTED_ORIGINS = [
    'https://webcore-studesprit.onrender.com',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# ALLOWED_HOSTS — PERFECT
ALLOWED_HOSTS = [
    'webcore-studesprit.onrender.com',
    'localhost',
    '127.0.0.1',
]

APP_VERSION = "0.1.0"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps
    "core",
    "accounts",
    "dashboard",
    "ai",
    "library",
  "evenement",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Custom middleware that injects request.user from Mongo session
    "core.middleware.SessionUserMiddleware",
]

ROOT_URLCONF = "main.urls"

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
                "core.context_processors.global_context",
            ],
        },
    }
]

WSGI_APPLICATION = "main.wsgi.application"


DATABASES = {
    "default": {
        # Use a lightweight sqlite3 database for Django ORM-backed apps in development.
        # The project primarily uses MongoDB for most data, but some apps (events, admin)
        # still rely on Django models, so provide a local sqlite DB to avoid
        # "ENGINE" misconfiguration errors during template rendering or admin use.
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Sessions: signed cookie sessions to avoid DB dependency
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"

# Security headers (basic). TODO: Harden for production and add CSP once static domains are finalized.
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"

# Authentication backends: include custom Mongo backend first
AUTHENTICATION_BACKENDS = [
    "core.auth_backend.MongoAuthBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# Tailwind build output directory (served as static)
# Tailwind CLI should build to static/build/tailwind.css

# Media files (user uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# MongoDB env
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "studesprit")

# Google OAuth2
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

# OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Configure logging without Django's DEFAULT_LOGGING (avoids mail_admins)
LOGGING_CONFIG = None
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
logging.config.dictConfig(LOGGING)
