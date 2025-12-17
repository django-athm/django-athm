# Installation

## Install the Package

```bash
pip install django-athm
```

## Configure Django Settings

Add the package to `INSTALLED_APPS` and configure your ATH Móvil tokens:

```python
INSTALLED_APPS = [
    # ...
    "django_athm",
]

DJANGO_ATHM_PUBLIC_TOKEN = "your-public-token"
DJANGO_ATHM_PRIVATE_TOKEN = "your-private-token"
```

Find your tokens in the ATH Móvil Business app under **Settings > Development > API Keys**.

!!! warning
    Never commit tokens to version control. Use environment variables or a secrets manager.

## Add URL Configuration

Include the URL patterns in your root `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    # ...
    path("athm/", include("django_athm.urls")),
]
```

This exposes:

- `/athm/webhook/` - Webhook endpoint for ATH Móvil events
- `/athm/api/` - Payment API endpoints (used by the template tag)

## Run Migrations

Create the database tables:

```bash
python manage.py migrate django_athm
```

## Install Webhook URL

Register your webhook URL with ATH Móvil. See [Webhooks](webhooks.md) for details.

## Verify Installation

Check that the admin interface is accessible at `/admin/django_athm/`.
