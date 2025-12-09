# django-athm

![Build Status](https://github.com/django-athm/django-athm/actions/workflows/test.yaml/badge.svg)
[![codecov](https://codecov.io/github/django-athm/django-athm/graph/badge.svg?token=n1uO3iKBPG)](https://codecov.io/github/django-athm/django-athm)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-athm)
![PyPI - Django Version](https://img.shields.io/pypi/djversions/django-athm)
[![PyPI version](https://img.shields.io/pypi/v/django-athm.svg)](https://pypi.org/project/django-athm/)
[![Published on Django Packages](https://img.shields.io/badge/Published%20on-Django%20Packages-0c3c26)](https://djangopackages.org/packages/p/django-athm/)
[![Packaged with uv](https://img.shields.io/badge/package_manager-uv-blue.svg)](https://github.com/astral-sh/uv)
![License badge](https://img.shields.io/github/license/django-athm/django-athm.svg)

Django integration for ATH Móvil payments (Puerto Rico's mobile payment system).

_See this README in spanish: [README_ES.md](/README_ES.md)_

## Main Purpose

**Webhook-driven payment and refund synchronization**. ATH Móvil sends definitive transaction data via webhooks, providing complete audit trails with fees, net amounts, and customer information.

## Features

- **Webhook handling** with idempotency
- **Transaction persistence** with line items and refunds for complete audit trails
- **Read-only Django Admin** with refund actions and webhook management
- **Django signals** for payment lifecycle events (created, completed, failed, expired, refunded)
- **Optional payment button template tag** with zero-dependency JavaScript for quick integration

## Requirements

- Python 3.10+
- Django 5.1+

## Installation

```bash
pip install django-athm
```

Add to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_athm",
]
```

Add your ATH Móvil Business API tokens (find these in the mobile app's settings):

```python
DJANGO_ATHM_PUBLIC_TOKEN = "your-public-token"
DJANGO_ATHM_PRIVATE_TOKEN = "your-private-token"
```

Include the URLs:

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    # ...
    path("athm/", include("django_athm.urls")),
]
```

Run migrations:

```bash
python manage.py migrate django_athm
```

## Quick Start (using bundled `templatetag`)

### 1. Create a view with payment configuration

```python
# views.py
from django.shortcuts import render

def checkout(request):
    athm_config = {
        "total": 25.00,
        "subtotal": 23.36,
        "tax": 1.64,
        "metadata_1": "order-123",
        "items": [
            {"name": "Widget", "price": 23.36, "quantity": 1}
        ],
        "success_url": "/order/complete/",
        "failure_url": "/order/failed/",
    }
    return render(request, "checkout.html", {"ATHM_CONFIG": athm_config})
```

### 2. Add the payment button to your template

```django
{% load django_athm %}

<h1>Checkout</h1>
{% athm_button ATHM_CONFIG %}
```

### 3. Handle payment completion with signals

```python
# signals.py
from django.dispatch import receiver
from django_athm.signals import payment_completed

@receiver(payment_completed)
def handle_payment_completed(sender, payment, **kwargs):
    # Update your order status, send confirmation email, etc.
    print(f"Payment {payment.reference_number} completed for ${payment.total}")
```

## Architecture

### Webhook-Driven Synchronization

Webhooks provide definitive transaction data with idempotency guarantees:

```
ATH Móvil webhook -> Idempotent processing -> Payment/Refund sync -> Django signals
```

### Optional Modal Payment Flow

For quick integration, use the included template tag:

1. **Initiate**: User clicks button, backend creates payment via ATH Móvil API
2. **Confirm**: User confirms payment in ATH Móvil app
3. **Authorize**: Backend authorizes the confirmed payment
4. **Webhook**: ATH Móvil sends completion event with final details

```
User clicks    ->  Backend creates  ->  User confirms   ->  Backend authorizes  ->  Webhook received
ATH Móvil         payment (OPEN)        in app (CONFIRM)    payment (COMPLETED)     (final details)
button
```

You can also build your own payment UI and use only the webhook synchronization features.

## Webhooks

### Installing Webhooks

You can install your webhook URL via the Django Admin:

1. Navigate to **ATH Móvil Webhook Events** in the admin
2. Click **Install Webhooks** button
3. Enter your webhook URL (must be HTTPS): `https://yourdomain.com/athm/webhook/`

### Webhook Idempotency

All webhooks are processed idempotently using deterministic keys based on the event payload. Duplicate events are automatically detected and ignored.

## Django Admin

The package provides a read-only admin interface:

- **Payments**: View all transactions, filter by status/date, bulk refund action
- **Line Items**: View items associated with payments
- **Refunds**: View refund records
- **Webhook Events**: View webhook history, reprocess failed events, install webhooks

All models are read-only to preserve data integrity - payments can only be refunded, not edited.

## Optional Template Tag Configuration

The `athm_button` template tag is **optional** - you can build your own payment UI and use only the webhook features.

```python
athm_config = {
    # Required
    "total": 25.00,              # Payment amount (1.00 - 1500.00)

    # Optional
    "subtotal": 23.36,           # Subtotal for display
    "tax": 1.64,                 # Tax amount
    "metadata_1": "order-123",   # Custom field (max 40 chars)
    "metadata_2": "customer-456",# Custom field (max 40 chars)
    "items": [...],              # List of line items
    "theme": "btn",              # Button theme: btn, btn-dark, btn-light
    "lang": "es",                # Language: es, en
    "success_url": "/thanks/",   # Redirect on success (adds ?reference_number=...&ecommerce_id=...)
    "failure_url": "/failed/",   # Redirect on failure
}
```

## Signals

Subscribe to payment lifecycle events:

```python
from django_athm.signals import (
    payment_created,    # Payment initiated
    payment_completed,  # Payment successful
    payment_failed,     # Payment cancelled
    payment_expired,    # Payment expired
    refund_completed,   # Refund processed
)
```

## Development Setup

This project uses [uv](https://github.com/astral-sh/uv) for package management.

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Run tests
DJANGO_SETTINGS_MODULE=tests.settings pytest --cov django_athm

# Run full test matrix
tox

# Run linting
tox -e lint
```

## Legal

This project is **not** affiliated with or endorsed by [Evertec, Inc.](https://www.evertecinc.com/) or [ATH Móvil](https://portal.athMóvil.com/).

## Dependencies

- [athm-python](https://github.com/django-athm/athm-python) - ATH Móvil API client

## References

- [ATH Móvil Business API Documentation](https://developer.athMóvil.com/)
- [ATH Móvil Business Webhooks Documentation](https://github.com/evertec/athMóvil-webhooks)

## License

MIT License - see [LICENSE](LICENSE) for details.
