# Configuration

## Django Settings

### Required

```python
DJANGO_ATHM_PUBLIC_TOKEN = "your-public-token"
DJANGO_ATHM_PRIVATE_TOKEN = "your-private-token"
```

Find your tokens in the ATH Móvil Business app under **Settings > Development > API Keys**.

### Optional

```python
DJANGO_ATHM_WEBHOOK_URL = "https://yourdomain.com/athm/webhook/"
```

Set this if URL auto-detection doesn't work (e.g., behind a reverse proxy).

## Template Tag

The `athm_button` template tag renders the ATH Móvil checkout button.

```django
{% load django_athm %}
{% athm_button ATHM_CONFIG %}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `total` | Decimal | Amount to charge ($1.00 - $1,500.00) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `subtotal` | Decimal | - | Subtotal before tax |
| `tax` | Decimal | - | Tax amount |
| `metadata_1` | str | "" | Custom metadata (max 40 chars) |
| `metadata_2` | str | "" | Custom metadata (max 40 chars) |
| `items` | list | [] | Item list (see below) |
| `theme` | str | "btn" | "btn", "btn-dark", "btn-light" |
| `lang` | str | "es" | "es" or "en" |
| `success_url` | str | "" | Redirect URL on success |
| `failure_url` | str | "" | Redirect URL on failure |

### Items

Each item in the `items` list:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | Item name |
| `description` | str | No | Item description |
| `quantity` | int | No | Quantity (default: 1) |
| `price` | Decimal | Yes | Price per item |
| `tax` | Decimal | No | Tax for this item |
| `metadata` | str | No | Item metadata |

### Success URL Parameters

On successful payment, query parameters are appended to `success_url`:

- `reference_number` - ATH Móvil reference number
- `ecommerce_id` - Transaction ID

Example: `/success/` becomes `/success/?reference_number=ABC123&ecommerce_id=uuid`

### Example

```python
context = {
    "ATHM_CONFIG": {
        "total": 25.00,
        "subtotal": 24.00,
        "tax": 1.00,
        "metadata_1": "Order #12345",
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
        "failure_url": "/checkout/",
        "lang": "es",
    }
}
```

## URL Endpoints

All endpoints under `django_athm:` namespace.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/` | POST | Receives ATH Móvil webhook events |
| `/api/initiate/` | POST | Creates new payment |
| `/api/status/` | GET | Polls payment status |
| `/api/authorize/` | POST | Confirms payment |
| `/api/cancel/` | POST | Cancels pending payment |

## Management Commands

### install_webhook

Register webhook URL with ATH Móvil.

```bash
# Auto-detect from setting
python manage.py install_webhook

# Explicit URL
python manage.py install_webhook https://yourdomain.com/athm/webhook/
```

URL must use HTTPS.

### athm_sync

Reconcile local records with ATH Móvil.

```bash
python manage.py athm_sync --from-date 2025-01-01 --to-date 2025-01-31

# Preview without modifying
python manage.py athm_sync --from-date 2025-01-01 --to-date 2025-01-31 --dry-run
```

See [Reconciliation](reconciliation.md) for details.

## Internationalization

The template tag supports Spanish and English:

```python
"lang": "es"  # Spanish (default)
"lang": "en"  # English
```

Configure Django's `LANGUAGE_CODE` for admin interface localization:

```python
USE_I18N = True
LANGUAGE_CODE = "es"  # or "en-us"
```
