# Configuration

## Django Settings

The following settings can be configured in your Django `settings.py`:

### DJANGO_ATHM_PUBLIC_TOKEN

Your public token from the ATH Movil Business app.

* Type: String
* Required: Yes
* Default: `None`

### DJANGO_ATHM_PRIVATE_TOKEN

Your private token from the ATH Movil Business app.

* Type: String
* Required: Yes
* Default: `None`

## athm_button Template Tag

The `athm_button` template tag renders the ATH Movil checkout button with an integrated payment modal. Pass a configuration dictionary with the following options:

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

- `reference_number`: The ATH Movil reference number
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
| `/webhook/` | POST | Receives ATH Movil webhook events |
| `/api/initiate/` | POST | Creates new payment |
| `/api/status/` | GET | Polls payment status |
| `/api/authorize/` | POST | Confirms payment with auth_token |
| `/api/cancel/` | POST | Cancels pending payment |

## Management Commands

### install_webhook

Registers a webhook URL with ATH Movil to receive payment events.

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
