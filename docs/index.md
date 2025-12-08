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

Add the URL patterns to your root `urls.py`:

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

@requires_csrf_token
def checkout_view(request):
    context = {
        "ATHM_CONFIG": {
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
            "success_url": "/checkout/success/",
            "failure_url": "/checkout/failure/",
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

django-athm uses a backend-first modal flow:

1. Customer clicks the ATH Movil checkout button
2. Modal opens and prompts for phone number
3. Backend creates payment via ATH Movil API (`/api/initiate/`)
4. Customer receives push notification on their ATH Movil app
5. Customer approves the payment in their app
6. Frontend polls for status changes (`/api/status/`)
7. Backend authorizes the payment (`/api/authorize/`)
8. ATH Movil sends webhook with final transaction details
9. Your application responds to payment events via [signals](signals.md)

## Accessing Transaction Data

Query payments from the database:

```python
from django_athm.models import Payment, PaymentLineItem, Refund

# Get all payments
payments = Payment.objects.all()

# Get completed payments
completed = Payment.objects.filter(status=Payment.Status.COMPLETED)

# Get a payment with its line items
payment = Payment.objects.prefetch_related("items").get(ecommerce_id=uuid)

# Access line items
for item in payment.items.all():
    print(f"{item.name}: ${item.price}")

# Check if refundable
if payment.is_refundable:
    print(f"Can refund up to ${payment.refundable_amount}")
```

## Django Admin

The package includes read-only admin views for:

- Viewing payment details
- Processing refunds on completed payments
- Viewing and reprocessing webhook events
- Installing webhook URLs with ATH Movil

## Management Commands

### install_webhook

Register a webhook URL with ATH Movil to receive payment events:

```bash
python manage.py install_webhook https://yourdomain.com/athm/webhook/
```

## Next Steps

- [Configuration Reference](config.md) - All settings and options
- [API Reference](api.md) - Models, fields, and services
- [Signals](signals.md) - Respond to payment events
- [Upgrading](upgrading.md) - Migration guide for new versions
