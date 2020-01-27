import os

DEBUG = True

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = os.path.dirname(PROJECT_DIR)

DJANGO_ATHM_PUBLIC_TOKEN = "public-token"
DJANGO_ATHM_PRIVATE_TOKEN = "private-token"
DJANGO_ATHM_SANDBOX_MODE = True

SECRET_KEY = "its-a-secret-to-everybody"

SITE_ID = 1

TIME_ZONE = "UTC"

USE_TZ = True

ROOT_URLCONF = "tests.urls"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    "django_athm",
    "tests",
    "tests.apps.testapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        "TEST": {"NAME": os.path.join(BASE_DIR, "test_db.sqlite3")},
    }
}

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

STATIC_URL = "/static/"
STATICFILES_DIRS = [
    os.path.join(PROJECT_DIR, "static"),
]
