"""
Django settings for CodeSentinel AI.

All configuration is read from environment variables.
A .env file in the backend/ directory is loaded automatically.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend directory if present
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-in-production",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# ── Applications ────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "corsheaders",
    "rest_framework",
    "apps.reviews",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ── Templates (minimal — API only) ──────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

# ── Database ─────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173"
).split(",")
CORS_ALLOW_ALL_ORIGINS = DEBUG  # permissive in dev

# ── REST Framework ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
}

# ── LLM settings ─────────────────────────────────────────────────────────────
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# AWS Bedrock settings
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
AWS_PROFILE = os.environ.get("AWS_PROFILE", "eazyq-prod")
BEDROCK_MODEL_REASONING = os.environ.get("BEDROCK_MODEL_REASONING", "apac.anthropic.claude-sonnet-4-6-v1:0")
BEDROCK_MODEL_PLANNING = os.environ.get("BEDROCK_MODEL_PLANNING", "apac.anthropic.claude-opus-4-8-v1:0")
BEDROCK_MODEL_ROUTING = os.environ.get("BEDROCK_MODEL_ROUTING", "apac.anthropic.claude-haiku-4-5-v1:0")

# ── MCP Server ───────────────────────────────────────────────────────────────
# Absolute path to the MCP server script.
# Default: resolve relative to this settings file → project root → mcp_server/server.py
_PROJECT_ROOT = BASE_DIR.parent
MCP_SERVER_SCRIPT: str = os.environ.get(
    "MCP_SERVER_SCRIPT",
    str(_PROJECT_ROOT / "mcp_server" / "server.py"),
)

# ── Review / Context Config ──────────────────────────────────────────────────
CONTEXT_WINDOW_LINES: int = int(os.environ.get("CONTEXT_WINDOW_LINES", "20"))
CONTEXT_MAX_TOKENS: int = int(os.environ.get("CONTEXT_MAX_TOKENS", "8000"))

# ── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "sentinel": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}
AWS_BEARER_TOKEN_BEDROCK = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")

# ── Iterative Reviewer Loop Config ────────────────────────────────────────────
ITERATIVE_MAX_ITERATIONS: int = int(os.environ.get("ITERATIVE_MAX_ITERATIONS", "5"))
ITERATIVE_MAX_TOOL_CALLS: int = int(os.environ.get("ITERATIVE_MAX_TOOL_CALLS", "5"))
ITERATIVE_MAX_TOTAL_TOOL_CALLS: int = int(os.environ.get("ITERATIVE_MAX_TOTAL_TOOL_CALLS", "10"))
ITERATIVE_REVIEW_TIMEOUT_SECONDS: int = int(os.environ.get("ITERATIVE_REVIEW_TIMEOUT_SECONDS", "180"))
ITERATIVE_MAX_TOOL_RESULT_CHARS: int = int(os.environ.get("ITERATIVE_MAX_TOOL_RESULT_CHARS", "12000"))
ITERATIVE_MAX_REPEATED_TOOL_CALLS: int = int(os.environ.get("ITERATIVE_MAX_REPEATED_TOOL_CALLS", "1"))

