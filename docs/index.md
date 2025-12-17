# django-athm

Django integration for ATH Móvil payments with webhook-driven synchronization.

## Features

- **Webhook handling** with SHA-256 idempotency
- **Transaction persistence** for payments, refunds, and customer records
- **Django signals** for payment lifecycle events
- **Read-only Django Admin** with refund actions and webhook management
- **Transaction reconciliation** via the `athm_sync` management command
- **Optional payment UI** via the `athm_button` template tag

## Requirements

- Python 3.10 - 3.14
- Django 5.1 - 6.0

## Quick Install

```bash
pip install django-athm
```

```python
INSTALLED_APPS = [
    # ...
    "django_athm",
]

DJANGO_ATHM_PUBLIC_TOKEN = "your-public-token"
DJANGO_ATHM_PRIVATE_TOKEN = "your-private-token"
```

```bash
python manage.py migrate django_athm
```

## Next Steps

- [Installation](installation.md) - Complete setup guide
- [Quickstart](quickstart.md) - Get up and running in minutes
- [Webhooks](webhooks.md) - Configure webhook handling
