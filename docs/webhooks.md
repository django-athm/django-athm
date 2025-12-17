# Webhooks

Webhooks are the primary data source for payment and refund records. ATH Móvil sends webhook events containing canonical transaction data including fees, net amounts, and customer information.

## Installing Webhooks

### Using Django Admin (Recommended)

The admin interface auto-detects your webhook URL from the current request:

1. Navigate to **Django Admin > Webhook Events**
2. Click **Install Webhooks**
3. Verify the auto-detected URL
4. Click **Submit**

### Using the Management Command

For automated deployments:

```bash
# Auto-detect from DJANGO_ATHM_WEBHOOK_URL setting
python manage.py install_webhook

# Or provide explicit URL
python manage.py install_webhook https://yourdomain.com/athm/webhook/
```

## Webhook URL Configuration

If URL auto-detection doesn't work (e.g., behind a reverse proxy), configure explicitly:

```python
DJANGO_ATHM_WEBHOOK_URL = "https://yourdomain.com/athm/webhook/"
```

## Idempotency

Each webhook event generates a deterministic idempotency key:

| Event Type | Key Formula |
|------------|-------------|
| eCommerce events | `sha256(ecommerceId:status)` |
| Refunds | `sha256(refund:referenceNumber)` |
| Other | `sha256(transactionType:referenceNumber)` |

A database unique constraint on `idempotency_key` ensures events are processed exactly once.

## Custom Webhook Views

To add custom logic before or after webhook processing:

```python
from django.views.decorators.csrf import csrf_exempt
from django_athm.views import process_webhook_request

@csrf_exempt
def my_webhook(request):
    # Pre-processing
    log_webhook_received(request)

    # Process webhook (idempotent)
    response = process_webhook_request(request)

    # Post-processing
    send_slack_notification()

    return response
```

Register in `urls.py`:

```python
urlpatterns = [
    path("athm/custom-webhook/", my_webhook, name="custom_webhook"),
]
```

Then install this URL with ATH Móvil instead of the default.

!!! note
    `process_webhook_request()` always returns HTTP 200, even on errors. This prevents webhook retries for non-recoverable errors.

## Event Types

| Event | Description |
|-------|-------------|
| `ecommerce_completed` | Payment successfully completed |
| `ecommerce_cancelled` | Customer cancelled in ATH Móvil app |
| `ecommerce_expired` | Payment session timed out |
| `refund` | Refund processed |
| `payment` | Non-ecommerce payment (ignored) |
| `donation` | Donation received (ignored) |
| `simulated` | Test event (ignored) |
