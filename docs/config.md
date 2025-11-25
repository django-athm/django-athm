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

A Django view that receives the POST request with payment data after a transaction completes, is cancelled, or expires. The default callback creates `ATHM_Transaction` and `ATHM_Item` objects from the request data.

* Type: Callable or import path string
* Required: No
* Default: `django_athm.views.default_callback`

**Example with custom callback:**

```python
DJANGO_ATHM_CALLBACK_VIEW = "myapp.views.my_payment_callback"
```

## athm_button Template Tag

The `athm_button` template tag renders the ATH Móvil checkout button. Pass a configuration dictionary with the following options:

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `total` | float | Total amount to charge. Must be between $1.00 and $1,500.00 |
| `subtotal` | float | Subtotal before tax |
| `tax` | float | Tax amount |
| `items` | list | List of item dictionaries (see Items section below) |
| `metadata_1` | string | Required metadata field (max 40 characters, auto-truncated) |
| `metadata_2` | string | Required metadata field (max 40 characters, auto-truncated) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
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
