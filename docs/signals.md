# Signals

Django signals notify your application of payment events. Use them to trigger business logic like confirmation emails, order status updates, or logging.

All signals are webhook-triggered and aligned with ATH Móvil's event names.

## Available Signals

| Signal | When Fired | Arguments |
|--------|------------|-----------|
| `payment_completed` | Payment successfully completed | `payment` |
| `payment_cancelled` | Customer cancelled in ATH Móvil app | `payment` |
| `payment_expired` | Payment session timed out | `payment` |
| `refund_sent` | Refund processed | `refund`, `payment` |

Import from `django_athm.signals`:

```python
from django_athm.signals import (
    payment_completed,
    payment_cancelled,
    payment_expired,
    refund_sent,
)
```

## Connecting Handlers

Use the `@receiver` decorator:

```python
from django.dispatch import receiver
from django_athm.signals import payment_completed

@receiver(payment_completed)
def handle_payment(sender, payment, **kwargs):
    order = Order.objects.get(reference=payment.metadata_1)
    order.status = "paid"
    order.save()
    send_confirmation_email(order)
```

## Complete Example

```python
# myapp/signals.py
import logging
from django.dispatch import receiver
from django_athm.signals import (
    payment_completed,
    payment_cancelled,
    payment_expired,
    refund_sent,
)

logger = logging.getLogger(__name__)

@receiver(payment_completed)
def on_payment_completed(sender, payment, **kwargs):
    logger.info(f"Payment completed: {payment.reference_number}")
    # Update order status, send confirmation email, trigger fulfillment

@receiver(payment_cancelled)
def on_payment_cancelled(sender, payment, **kwargs):
    logger.warning(f"Payment cancelled: {payment.ecommerce_id}")
    # Release inventory, notify customer

@receiver(payment_expired)
def on_payment_expired(sender, payment, **kwargs):
    logger.warning(f"Payment expired: {payment.ecommerce_id}")
    # Notify customer, offer retry

@receiver(refund_sent)
def on_refund_sent(sender, refund, payment, **kwargs):
    logger.info(f"Refund sent: ${refund.amount} for {payment.reference_number}")
    # Update order status, send refund confirmation
```

## Registering Handlers

Import your signals module in your app's `ready()` method:

```python
# myapp/apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = "myapp"

    def ready(self):
        import myapp.signals  # noqa: F401
```

## Signal Arguments

### payment_completed, payment_cancelled, payment_expired

| Argument | Type | Description |
|----------|------|-------------|
| `sender` | class | `Payment` |
| `payment` | `Payment` | The payment instance |

### refund_sent

| Argument | Type | Description |
|----------|------|-------------|
| `sender` | class | `Refund` |
| `refund` | `Refund` | The refund instance |
| `payment` | `Payment` | The related payment |
