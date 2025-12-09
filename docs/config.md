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

### DJANGO_ATHM_WEBHOOK_URL

Your webhook URL for receiving ATH Móvil payment events. Optional - the admin interface auto-detects from the current request.

* Type: String (HTTPS URL)
* Required: No
* Default: `None`

**When to set this:**
- You want to explicitly control the webhook URL
- Your app runs behind a reverse proxy and URL detection doesn't work correctly
- You're using the management command without the admin interface

**Example:**
```python
DJANGO_ATHM_WEBHOOK_URL = "https://yourdomain.com/athm/webhook/"
```

## Webhook Configuration

### Using the Admin Interface (Recommended)

The admin interface automatically detects your webhook URL from the current request. No configuration needed.

1. Navigate to Django Admin > Webhook Events
2. Click "Install Webhooks" button
3. Verify the auto-detected URL
4. Click "Submit" to register with ATH Móvil

### Using the Management Command

For automated deployments or when the admin interface isn't available:

**With setting configured:**
```bash
python manage.py install_webhook
```

**With explicit URL:**
```bash
python manage.py install_webhook https://yourdomain.com/athm/webhook/
```

### Custom Webhook Views

If you need to add custom logic before or after webhook processing, you can wrap the built-in webhook handler:

```python
from django.views.decorators.csrf import csrf_exempt
from django_athm.views import process_webhook_request

@csrf_exempt
def my_custom_webhook(request):
    # Pre-processing (e.g., logging, rate limiting)
    log_webhook_received(request)

    # Call django-athm webhook handler (maintains idempotency)
    response = process_webhook_request(request)

    # Post-processing (e.g., notifications, analytics)
    send_slack_notification()

    return response
```

Register your custom webhook in `urls.py`:
```python
urlpatterns = [
    path("athm/custom-webhook/", my_custom_webhook, name="custom_webhook"),
]
```

Then register it with ATH Móvil using the URL to your custom view.

## athm_button Template Tag

The `athm_button` template tag renders the ATH Móvil checkout button with an integrated payment modal. Pass a configuration dictionary with the following options:

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `total` | float | Total amount to charge. Must be between $1.00 and $1,500.00 |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `subtotal` | float | - | Subtotal before tax (for display) |
| `tax` | float | - | Tax amount |
| `metadata_1` | string | "" | Custom metadata field (max 40 chars, auto-truncated) |
| `metadata_2` | string | "" | Custom metadata field (max 40 chars, auto-truncated) |
| `items` | list | [] | List of item dictionaries (see Items section below) |
| `theme` | string | "btn" | Button theme |
| `lang` | string | "es" | Language code ("es" or "en") |
| `success_url` | string | "" | Redirect URL on success (query params appended) |
| `failure_url` | string | "" | Redirect URL on failure |

### Items

Each item in the `items` list should be a dictionary with:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Item name |
| `description` | string | No | Item description |
| `quantity` | int | No | Quantity (default: 1) |
| `price` | float | Yes | Price per item |
| `tax` | float | No | Tax for this item |
| `metadata` | string | No | Item metadata |

### Success URL Query Parameters

When a payment completes successfully and `success_url` is provided, the user is redirected with query parameters appended:

- `reference_number`: The ATH Móvil reference number
- `ecommerce_id`: The eCommerce transaction ID

Example: `/checkout/success/` becomes `/checkout/success/?reference_number=ABC123&ecommerce_id=uuid-here`

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
        "success_url": "/checkout/success/",
        "failure_url": "/checkout/failure/",
        "lang": "es",
    }
}
```

## URL Endpoints

All endpoints are namespaced under `django_athm:`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/` | POST | Receives ATH Móvil webhook events |
| `/api/initiate/` | POST | Creates new payment |
| `/api/status/` | GET | Polls payment status |
| `/api/authorize/` | POST | Confirms payment with auth_token |
| `/api/cancel/` | POST | Cancels pending payment |

## Management Commands

### install_webhook

Registers a webhook URL with ATH Móvil to receive payment events.

```bash
python manage.py install_webhook https://yourdomain.com/athm/webhook/
```

The URL must use HTTPS. This is the same functionality available in the Django Admin under Webhook Events > Install Webhooks.

## Internationalization

django-athm includes translations for Spanish (es) and English (en). To enable translations:

### Django Settings

```python
USE_I18N = True
LANGUAGE_CODE = "es"  # or "en-us"
```

### Button Language

The `athm_button` template tag accepts a `lang` parameter:

```python
context = {
    "ATHM_CONFIG": {
        "total": 25.00,
        "lang": "es",  # "es" or "en"
        # ... other fields
    }
}
```

The button UI text (phone prompt, status messages) will display in the selected language.

### Supported Languages

| Code | Language |
|------|----------|
| `es` | Spanish |
| `en` | English |
