# Signals

django-athm provides Django signals to notify your application of payment events. Use these to trigger business logic like sending confirmation emails, updating order status, or logging events.

## Receiving Transaction Updates

django-athm provides two ways to receive transaction updates from ATH Movil:

| Approach | Best For | Complexity |
|----------|----------|------------|
| **Signals** (recommended) | Most applications | Low |
| **Custom Callback** | Full control over request handling | Medium |

### Signals (Recommended)

Use Django signals when you want to:

- React to specific payment statuses (completed, cancelled)
- Keep your payment logic decoupled from callback processing
- Use the default transaction/item creation behavior

The default callback automatically dispatches signals after creating transaction records. Simply connect your handlers as shown below.

### Custom Callback

Use a custom callback when you need to:

- Modify how transactions are created or validated
- Integrate with external systems before saving data
- Implement custom authentication or request validation

**Important:** Custom callbacks must dispatch signals manually if you want signal handlers to run. See [Configuration - Custom Callback](config.md#django_athm_callback_view) for implementation details.

## Available Signals

All signals are available from `django_athm.signals`:

```python
from django_athm.signals import (
    athm_response_received,
    athm_completed_response,
    athm_cancelled_response,
    athm_expired_response,
)
```

### athm_response_received

Dispatched for **every** payment callback, regardless of status.

**When it fires:** After any payment response is received from ATH Movil.

**Use case:** Logging all payment attempts, analytics, or when you need to handle all responses uniformly.

### athm_completed_response

Dispatched when a payment is **successfully completed**.

**When it fires:** After the customer approves the payment in their ATH Movil app and the transaction is confirmed.

**Use case:** Send confirmation emails, update order status to "paid", trigger fulfillment.

### athm_cancelled_response

Dispatched when a payment is **cancelled** by the customer.

**When it fires:** When the customer declines or cancels the payment in their ATH Movil app.

**Use case:** Release reserved inventory, notify customer of cancellation.

### athm_expired_response

Dispatched when a payment **times out** before the customer completes it.

**When it fires:** When the checkout session expires (after the configured timeout, default 600 seconds).

**Use case:** Distinguish between explicit user cancellation and session timeout, implement retry logic for expired sessions.

## Connecting to Signals

Use Django's `@receiver` decorator to connect your handlers:

```python
from django.dispatch import receiver
from django_athm.signals import athm_completed_response, athm_cancelled_response

@receiver(athm_completed_response)
def handle_payment_completed(sender, **kwargs):
    """Handle successful payment."""
    transaction = kwargs.get("transaction")

    # Update your order status
    order = Order.objects.get(reference=transaction.metadata_1)
    order.status = "paid"
    order.save()

    # Send confirmation email
    send_confirmation_email(order)

@receiver(athm_cancelled_response)
def handle_payment_cancelled(sender, **kwargs):
    """Handle cancelled payment."""
    transaction = kwargs.get("transaction")

    # Release reserved inventory
    order = Order.objects.get(reference=transaction.metadata_1)
    order.release_inventory()
```

## Signal Arguments

All signals send the following keyword arguments:

| Argument | Type | Description |
|----------|------|-------------|
| `sender` | class | The sender class (typically the view) |
| `transaction` | `ATHM_Transaction` | The transaction object created from the callback |

## Example: Complete Signal Handler

```python
# myapp/signals.py
import logging
from django.dispatch import receiver
from django_athm.signals import (
    athm_response_received,
    athm_completed_response,
    athm_cancelled_response,
    athm_expired_response,
)

logger = logging.getLogger(__name__)

@receiver(athm_response_received)
def log_all_responses(sender, **kwargs):
    """Log all payment responses for debugging."""
    transaction = kwargs.get("transaction")
    logger.info(
        f"ATH Movil response: {transaction.reference_number} "
        f"status={transaction.status}"
    )

@receiver(athm_completed_response)
def process_completed_payment(sender, **kwargs):
    """Process successful payments."""
    transaction = kwargs.get("transaction")
    logger.info(f"Payment completed: {transaction.reference_number}")

    # Your business logic here
    # - Update order status
    # - Send confirmation email
    # - Trigger fulfillment

@receiver(athm_cancelled_response)
def handle_cancelled_payment(sender, **kwargs):
    """Handle payment cancellations."""
    transaction = kwargs.get("transaction")
    logger.warning(f"Payment cancelled: {transaction.reference_number}")

    # Your business logic here
    # - Release inventory
    # - Notify customer

@receiver(athm_expired_response)
def handle_expired_payment(sender, **kwargs):
    """Handle expired checkout sessions."""
    transaction = kwargs.get("transaction")
    logger.warning(f"Payment expired: {transaction.reference_number}")

    # Your business logic here
    # - Notify customer about timeout
    # - Offer to retry payment
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
