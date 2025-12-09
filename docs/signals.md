# Signals

django-athm provides Django signals to notify your application of payment events. Use these to trigger business logic like sending confirmation emails, updating order status, or logging events.

## Available Signals

All signals are available from `django_athm.signals`:

```python
from django_athm.signals import (
    payment_created,
    payment_completed,
    payment_failed,
    payment_expired,
    refund_completed,
)
```

### payment_created

Dispatched when a new payment is initiated.

**When it fires:** After a Payment record is created via the initiate API endpoint.

**Use case:** Reserve inventory, create pending order records.

**Arguments:**
- `sender`: `Payment` class
- `payment`: The `Payment` instance

### payment_completed

Dispatched when a payment is successfully completed.

**When it fires:** After the webhook confirms a successful payment with final transaction details.

**Use case:** Send confirmation emails, update order status to "paid", trigger fulfillment.

**Arguments:**
- `sender`: `Payment` class
- `payment`: The `Payment` instance

### payment_failed

Dispatched when a payment is cancelled.

**When it fires:** When the payment is cancelled by the customer or merchant.

**Use case:** Release reserved inventory, notify customer of cancellation.

**Arguments:**
- `sender`: `Payment` class
- `payment`: The `Payment` instance

### payment_expired

Dispatched when a payment expires before completion.

**When it fires:** When the webhook indicates the payment session expired.

**Use case:** Distinguish between explicit cancellation and session timeout, implement retry logic.

**Arguments:**
- `sender`: `Payment` class
- `payment`: The `Payment` instance

### refund_completed

Dispatched when a refund is successfully processed.

**When it fires:** After a refund is confirmed by ATH Móvil.

**Use case:** Update order status, send refund confirmation email.

**Arguments:**
- `sender`: `Refund` class
- `refund`: The `Refund` instance
- `payment`: The related `Payment` instance

## Connecting to Signals

Use Django's `@receiver` decorator to connect your handlers:

```python
from django.dispatch import receiver
from django_athm.signals import payment_completed, payment_failed, refund_completed

@receiver(payment_completed)
def handle_payment_completed(sender, payment, **kwargs):
    """Handle successful payment."""
    # Update your order status
    order = Order.objects.get(reference=payment.metadata_1)
    order.status = "paid"
    order.save()

    # Send confirmation email
    send_confirmation_email(order)

@receiver(payment_failed)
def handle_payment_failed(sender, payment, **kwargs):
    """Handle cancelled payment."""
    # Release reserved inventory
    order = Order.objects.get(reference=payment.metadata_1)
    order.release_inventory()

@receiver(refund_completed)
def handle_refund_completed(sender, refund, payment, **kwargs):
    """Handle completed refund."""
    # Update order status
    order = Order.objects.get(reference=payment.metadata_1)
    order.status = "refunded"
    order.save()

    # Send refund confirmation
    send_refund_email(order, refund.amount)
```

## Example: Complete Signal Handler

```python
# myapp/signals.py
import logging
from django.dispatch import receiver
from django_athm.signals import (
    payment_created,
    payment_completed,
    payment_failed,
    payment_expired,
    refund_completed,
)

logger = logging.getLogger(__name__)

@receiver(payment_created)
def log_payment_created(sender, payment, **kwargs):
    """Log new payment initiation."""
    logger.info(
        f"Payment initiated: {payment.ecommerce_id} "
        f"total=${payment.total}"
    )

@receiver(payment_completed)
def process_completed_payment(sender, payment, **kwargs):
    """Process successful payments."""
    logger.info(f"Payment completed: {payment.reference_number}")

    # Your business logic here
    # - Update order status
    # - Send confirmation email
    # - Trigger fulfillment

@receiver(payment_failed)
def handle_cancelled_payment(sender, payment, **kwargs):
    """Handle payment cancellations."""
    logger.warning(f"Payment cancelled: {payment.ecommerce_id}")

    # Your business logic here
    # - Release inventory
    # - Notify customer

@receiver(payment_expired)
def handle_expired_payment(sender, payment, **kwargs):
    """Handle expired checkout sessions."""
    logger.warning(f"Payment expired: {payment.ecommerce_id}")

    # Your business logic here
    # - Notify customer about timeout
    # - Offer to retry payment

@receiver(refund_completed)
def handle_refund(sender, refund, payment, **kwargs):
    """Handle completed refunds."""
    logger.info(
        f"Refund completed: ${refund.amount} for payment {payment.reference_number}"
    )
```

## Registering Signal Handlers

Ensure your signal handlers are loaded by importing them in your app's `ready()` method:

```python
# myapp/apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = "myapp"

    def ready(self):
        import myapp.signals  # noqa: F401
```
