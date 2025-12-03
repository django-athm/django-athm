# Getting Started

## Installation

Install the package from PyPI:

```bash
pip install django-athm
```

Add the package to your `INSTALLED_APPS` and configure the required settings in your `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    "django_athm",
]

DJANGO_ATHM_PUBLIC_TOKEN = "your-public-token"
DJANGO_ATHM_PRIVATE_TOKEN = "your-private-token"
```

Run migrations to create the database tables:

```bash
python manage.py migrate
```

## URL Configuration

Add the callback URL to your root `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    # ...
    path("athm/", include("django_athm.urls", namespace="django_athm")),
]
```

## Displaying the Checkout Button

### 1. Create the Configuration in Your View

```python
from django.views.decorators.csrf import requires_csrf_token
from django_athm.constants import BUTTON_COLOR_DEFAULT, BUTTON_LANGUAGE_SPANISH

@requires_csrf_token
def checkout_view(request):
    context = {
        "ATHM_CONFIG": {
            "theme": BUTTON_COLOR_DEFAULT,
            "language": BUTTON_LANGUAGE_SPANISH,
            "total": 25.00,
            "subtotal": 24.00,
            "tax": 1.00,
            "metadata_1": "Order #12345",
            "metadata_2": "Customer reference",
            "items": [
                {
                    "name": "Product Name",
                    "description": "Product description",
                    "quantity": 1,
                    "price": 24.00,
                    "tax": 1.00,
                }
            ],
        }
    }
    return render(request, "checkout.html", context)
```

### 2. Render the Button in Your Template

```html
{% load django_athm %}

{% athm_button ATHM_CONFIG %}
```

The CSRF token must be available in your template. Use the `@requires_csrf_token` decorator on your view as shown above.

## Payment Flow

1. Customer clicks the ATH Movil checkout button
2. The ATH Movil modal opens and prompts the customer for their phone number
3. Customer receives a push notification on their ATH Movil app
4. Customer approves (or cancels) the payment in their app
5. django-athm receives a callback and creates a transaction record
6. Your application responds to payment events via [signals](signals.md) or a [custom callback](config.md#django_athm_callback_view)

## Accessing Transaction Data

Query transactions and items from the database:

```python
from django_athm.models import ATHM_Transaction, ATHM_Item

# Get all transactions
transactions = ATHM_Transaction.objects.all()

# Get completed transactions
completed = ATHM_Transaction.objects.completed()

# Get refundable transactions
refundable = ATHM_Transaction.objects.refundable()

# Get transactions with items prefetched
with_items = ATHM_Transaction.objects.with_items()

# Filter by date range
from datetime import datetime
recent = ATHM_Transaction.objects.by_date_range(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 1, 31)
)
```

## Django Admin

The package includes admin views for managing transactions. You can:

- View transaction details
- Refund completed transactions
- Sync transaction data with ATH Movil API

## Management Commands

### athm_sync

Synchronize your database with transactions from ATH Movil:

```bash
python manage.py athm_sync --start "2025-01-01 00:00:00" --end "2025-01-31 23:59:59"
```

## Next Steps

- [Configuration Reference](config.md) - All settings and options
- [API Reference](api.md) - Models, methods, and QuerySets
- [Signals](signals.md) - Respond to payment events
- [Upgrading](upgrading.md) - Migration guide for new versions
