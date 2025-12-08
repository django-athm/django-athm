# Configuration

## Django Settings

The following settings can be configured in your Django `settings.py`:

### DJANGO_ATHM_PUBLIC_TOKEN

Your public token from the ATH Móvil Business app.

* Type: String
* Required: Yes
* Default: `None`

### DJANGO_ATHM_PRIVATE_TOKEN

Your private token from the ATH Móvil Business app.

* Type: String
* Required: Yes
* Default: `None`

### DJANGO_ATHM_CALLBACK_VIEW

A Django view that receives the POST request with payment data after a transaction completes, is cancelled, or expires.

* Type: Callable or import path string
* Required: No
* Default: `django_athm.views.default_callback`

**What the default callback does:**

1. Parses POST data from ATH Movil
2. Creates `ATHM_Transaction` and `ATHM_Item` records
3. Creates or updates `ATHM_Client` records if customer info is provided
4. Dispatches [signals](signals.md) for your handlers to respond

**Example with custom callback:**

```python
# settings.py
DJANGO_ATHM_CALLBACK_VIEW = "myapp.views.my_payment_callback"
```

#### Implementing a Custom Callback

If you need full control over callback processing, implement a custom view:

```python
# myapp/views.py
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction

from django_athm.models import ATHM_Transaction
from django_athm.signals import (
    athm_response_received,
    athm_completed_response,
    athm_cancelled_response,
    athm_expired_response,
)

@csrf_exempt
@require_POST
@transaction.atomic
def my_payment_callback(request):
    """Custom callback with manual signal dispatch."""
    reference_number = request.POST.get("referenceNumber")
    total = request.POST.get("total")
    status = request.POST.get("ecommerceStatus", "COMPLETED")

    if not reference_number or not total:
        return JsonResponse({"error": "Missing required fields"}, status=400)

    # Your custom validation/processing logic here

    transaction_obj = ATHM_Transaction.objects.create(
        reference_number=reference_number,
        total=float(total),
        status=ATHM_Transaction.Status.COMPLETED,
        # ... other fields as needed
    )

    # Dispatch signals manually if you want handlers to run
    athm_response_received.send(
        sender=ATHM_Transaction,
        transaction=transaction_obj,
    )

    if status == "COMPLETED":
        athm_completed_response.send(
            sender=ATHM_Transaction,
            transaction=transaction_obj,
        )
    elif status == "EXPIRED":
        athm_expired_response.send(
            sender=ATHM_Transaction,
            transaction=transaction_obj,
        )
    elif status in ("CANCEL", "CANCELLED"):
        athm_cancelled_response.send(
            sender=ATHM_Transaction,
            transaction=transaction_obj,
        )

    return HttpResponse(status=201)
```

**Note:** The `@csrf_exempt` decorator is required because ATH Movil sends callbacks without CSRF tokens.

## athm_button Template Tag

The `athm_button` template tag renders the ATH Móvil checkout button. Pass a configuration dictionary with the following options:

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `total` | float | Total amount to charge. Must be between $1.00 and $1,500.00 |
| `items` | list | List of item dictionaries (see Items section below). At least one item required. |
| `metadata_1` | string | Required metadata field (max 40 characters, auto-truncated) |
| `metadata_2` | string | Required metadata field (max 40 characters, auto-truncated) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `subtotal` | float | 0 | Subtotal before tax |
| `tax` | float | 0 | Tax amount |
| `public_token` | string | `DJANGO_ATHM_PUBLIC_TOKEN` | Override the public token for this transaction |
| `timeout` | int | 600 | Seconds before checkout times out (120-600) |

### Items

Each item in the `items` list should be a dictionary with:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Item name (max 32 characters) |
| `description` | string | Yes | Item description (max 128 characters) |
| `quantity` | int | Yes | Quantity |
| `price` | float | Yes | Price per item |
| `tax` | float | No | Tax for this item |
| `metadata` | string | No | Item metadata (max 40 characters) |

### Validation Rules

The template tag validates your configuration:

* **Total amount**: Must be between $1.00 and $1,500.00
* **Metadata fields**: Both `metadata_1` and `metadata_2` are required. Values exceeding 40 characters are automatically truncated with a warning logged.
* **Timeout**: Values outside 120-600 seconds default to 600 with a warning logged.

### Example Configuration

```python
context = {
    "ATHM_CONFIG": {
        "total": 25.00,
        "subtotal": 24.00,
        "tax": 1.00,
        "metadata_1": "Order #12345",
        "metadata_2": "Customer: John Doe",
        "items": [
            {
                "name": "Widget",
                "description": "A useful widget",
                "quantity": 1,
                "price": 24.00,
                "tax": 1.00,
            }
        ],
    }
}
```

## Known Limitations (ATH Móvil v4 API Bugs)

The ATH Móvil v4 API has several known bugs that affect functionality. django-athm works around these issues automatically:

### phone_number (BTRA_0041 Error)

Providing a `phone_number` in the configuration causes a `BTRA_0041` error from the ATH Móvil API. The checkout modal will always prompt the customer to enter their phone number regardless of whether you provide it.

**Workaround**: django-athm ignores any `phone_number` value you provide and logs a warning. Do not pass `phone_number` in your configuration.

### theme (Only "btn" Works)

The `theme` option is broken in the ATH Móvil v4 API. Only the default theme (`"btn"`) works. The `"btn-light"` and `"btn-dark"` themes are ignored by ATH Móvil.

**Workaround**: django-athm always uses `"btn"` regardless of the value you provide. If you pass a different theme, a warning is logged.

### language (Only "es" Works)

The `language` option is broken in the ATH Móvil v4 API. Only Spanish (`"es"`) works. The English option (`"en"`) is ignored by ATH Móvil.

**Workaround**: django-athm always uses `"es"` regardless of the value you provide. If you pass a different language, a warning is logged.

These limitations are on ATH Móvil's side. We will update django-athm when these issues are resolved.

## Management Commands

### install_webhook

Registers a webhook URL with ATH Movil to receive payment events.

```bash
python manage.py install_webhook https://yourdomain.com/athm/webhook/
```

The URL must use HTTPS. This is the same functionality available in the Django Admin under Webhook Events > Install Webhooks.
