# Services

High-level services for managing ATH Móvil payments. Import from `django_athm.services`.

## PaymentService

Orchestrates payment operations via the ATH Móvil API.

### initiate()

Create a new payment.

```python
from decimal import Decimal
from django_athm.services import PaymentService

payment, auth_token = PaymentService.initiate(
    total=Decimal("25.00"),
    phone_number="7871234567",
    subtotal=Decimal("24.00"),
    tax=Decimal("1.00"),
    metadata_1="Order #12345",
    metadata_2="Customer reference",
    items=[
        {
            "name": "Widget",
            "description": "A useful widget",
            "quantity": 1,
            "price": "24.00",
            "tax": "1.00",
        }
    ],
)
```

**Returns**: Tuple of (`Payment`, `auth_token`)

### find_status()

Check payment status with ATH Móvil.

```python
status = PaymentService.find_status(ecommerce_id)
```

**Returns**: Status string (`OPEN`, `CONFIRM`, `COMPLETED`, etc.)

### authorize()

Authorize a confirmed payment.

```python
reference_number = PaymentService.authorize(ecommerce_id, auth_token)
```

**Returns**: Reference number string

### cancel()

Cancel a pending payment.

```python
PaymentService.cancel(ecommerce_id)
```

### update_phone_number()

Update phone number for a pending payment.

```python
PaymentService.update_phone_number(
    ecommerce_id=uuid,
    phone_number="7871234567",
    auth_token=auth_token,
)
```

### refund()

Refund a completed payment. Defaults to full refund if amount not specified.

```python
from decimal import Decimal
from django_athm.services import PaymentService
from django_athm.models import Payment

payment = Payment.objects.get(reference_number="abc123")

# Full refund
refund = PaymentService.refund(payment)

# Partial refund
refund = PaymentService.refund(
    payment,
    amount=Decimal("10.00"),
    message="Partial refund"
)
```

**Raises `ValueError` if**:

- Payment is not refundable (not COMPLETED or fully refunded)
- Payment has no reference_number
- Refund amount is not positive
- Refund amount exceeds refundable amount

### sync_status()

Check remote status and update local payment if changed.

```python
from django_athm.models import Payment

payment = Payment.objects.get(ecommerce_id=uuid)
current_status = PaymentService.sync_status(payment)
```

**Returns**: Current status string

### fetch_transaction_report()

Fetch transaction report from ATH Móvil API.

```python
transactions = PaymentService.fetch_transaction_report(
    from_date="2025-01-01 00:00:00",
    to_date="2025-01-31 23:59:59",
)

for txn in transactions:
    print(f"{txn['referenceNumber']}: ${txn['total']}")
```

**Returns**: List of transaction dicts

Used internally by the `athm_sync` management command.

## WebhookProcessor

Handles webhook events with idempotency and ACID guarantees.

### store_event()

Store a webhook event with idempotency key.

```python
from django_athm.services import WebhookProcessor

event, created = WebhookProcessor.store_event(payload, remote_ip)
```

**Returns**: Tuple of (`WebhookEvent`, `created` bool)

### process()

Process a validated webhook event. Safe to call multiple times due to idempotency.

```python
WebhookProcessor.process(event, normalized_payload)
```

### mark_processed()

Mark an event as processed.

```python
WebhookProcessor.mark_processed(event)
```

## ClientService

Manages customer records.

### get_or_update()

Get or create a client by phone number, updating name/email if provided.

```python
from django_athm.services import ClientService

client = ClientService.get_or_update(
    phone_number="7871234567",
    name="John Doe",
    email="john@example.com"
)
```

**Returns**: `Client` instance or `None` if phone number is empty
