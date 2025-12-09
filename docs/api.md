# API Reference

## Models

### Payment

Represents a payment transaction from ATH Móvil.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `ecommerce_id` | UUIDField | Primary key - ATH Móvil eCommerce transaction ID |
| `reference_number` | CharField | Unique ATH Móvil reference number (populated on completion) |
| `daily_transaction_id` | CharField | ATH Móvil daily transaction ID |
| `status` | CharField | Payment status (see Status choices below) |
| `created` | DateTimeField | Record creation timestamp |
| `modified` | DateTimeField | Last modification timestamp |
| `transaction_date` | DateTimeField | Transaction completion date from ATH Móvil |
| `total` | DecimalField | Total transaction amount |
| `subtotal` | DecimalField | Subtotal before tax |
| `tax` | DecimalField | Tax amount |
| `fee` | DecimalField | ATH Móvil processing fee |
| `net_amount` | DecimalField | Net amount after fees |
| `total_refunded_amount` | DecimalField | Total amount refunded |
| `customer_name` | CharField | Customer name from ATH Móvil |
| `customer_phone` | CharField | Customer phone from ATH Móvil |
| `customer_email` | EmailField | Customer email from ATH Móvil |
| `metadata_1` | CharField | Custom metadata field (max 64 chars) |
| `metadata_2` | CharField | Custom metadata field (max 64 chars) |
| `message` | TextField | Optional message |
| `business_name` | CharField | Business name from ATH Móvil |

#### Status Choices

```python
class Status(models.TextChoices):
    OPEN = "OPEN"           # Payment initiated, awaiting customer confirmation
    CONFIRM = "CONFIRM"     # Customer confirmed, awaiting authorization
    COMPLETED = "COMPLETED" # Successfully completed
    CANCEL = "CANCEL"       # Cancelled
    EXPIRED = "EXPIRED"     # Expired before completion
```

#### Properties

```python
payment.is_successful    # True if status is COMPLETED
payment.is_refundable    # True if completed and has refundable amount remaining
payment.refundable_amount  # Decimal amount that can still be refunded
```

#### Example Usage

```python
from django_athm.models import Payment

# Get all payments
payments = Payment.objects.all()

# Get completed payments
completed = Payment.objects.filter(status=Payment.Status.COMPLETED)

# Get refundable payments
refundable = Payment.objects.filter(
    status=Payment.Status.COMPLETED,
    total__gt=models.F("total_refunded_amount")
)

# Get payment with line items
payment = Payment.objects.prefetch_related("items").get(ecommerce_id=uuid)

# Filter by date range
from datetime import datetime
recent = Payment.objects.filter(
    created__gte=datetime(2025, 1, 1),
    created__lte=datetime(2025, 1, 31)
)
```

---

### PaymentLineItem

Represents a line item in a payment transaction.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField | Primary key |
| `transaction` | ForeignKey | Related Payment |
| `name` | CharField | Item name (max 128 chars) |
| `description` | TextField | Item description |
| `quantity` | PositiveSmallIntegerField | Quantity |
| `price` | DecimalField | Price per item |
| `tax` | DecimalField | Tax for this item |
| `metadata` | CharField | Item metadata (max 64 chars) |

#### Example Usage

```python
from django_athm.models import Payment, PaymentLineItem

# Get all items for a payment
payment = Payment.objects.get(ecommerce_id=uuid)
items = payment.items.all()

# Query items directly
expensive_items = PaymentLineItem.objects.filter(price__gte=100)
```

---

### Refund

Represents a refund for a payment.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField | Primary key |
| `payment` | ForeignKey | Related Payment |
| `reference_number` | CharField | Unique ATH Móvil refund reference number |
| `daily_transaction_id` | CharField | ATH Móvil daily transaction ID |
| `amount` | DecimalField | Refund amount |
| `message` | CharField | Refund message (max 50 chars) |
| `status` | CharField | Refund status |
| `customer_name` | CharField | Customer name at time of refund |
| `customer_phone` | CharField | Customer phone at time of refund |
| `customer_email` | EmailField | Customer email at time of refund |
| `transaction_date` | DateTimeField | Refund transaction date |
| `created_at` | DateTimeField | Record creation timestamp |

#### Example Usage

```python
from django_athm.models import Payment, Refund

# Get all refunds for a payment
payment = Payment.objects.get(ecommerce_id=uuid)
refunds = payment.refunds.all()

# Query refunds directly
recent_refunds = Refund.objects.filter(created_at__gte=datetime(2025, 1, 1))
```

---

### WebhookEvent

Tracks webhook events received from ATH Móvil.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField | Primary key |
| `idempotency_key` | CharField | Unique key for deduplication |
| `event_type` | CharField | Type of webhook event |
| `remote_ip` | GenericIPAddressField | IP address of webhook request |
| `payload` | JSONField | Raw JSON payload |
| `processed` | BooleanField | Whether event was successfully processed |
| `transaction` | ForeignKey | Associated Payment (if any) |
| `created` | DateTimeField | Record creation timestamp |
| `modified` | DateTimeField | Last modification timestamp |

#### Event Types

```python
class Type(models.TextChoices):
    SIMULATED = "simulated"
    PAYMENT_RECEIVED = "payment"
    DONATION_RECEIVED = "donation"
    REFUND_SENT = "refund"
    ECOMMERCE_COMPLETED = "ecommerce_completed"
    ECOMMERCE_CANCELLED = "ecommerce_cancelled"
    ECOMMERCE_EXPIRED = "ecommerce_expired"
    UNKNOWN = "unknown"
```

---

## Services

### PaymentService

High-level service for managing ATH Móvil payments. Located at `django_athm.services.PaymentService`.

#### Methods

##### initiate()

Create a new payment with ATH Móvil.

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

##### find_status()

Check the current status of a payment with ATH Móvil.

```python
from django_athm.services import PaymentService

status = PaymentService.find_status(ecommerce_id)
```

##### authorize()

Authorize a confirmed payment.

```python
from django_athm.services import PaymentService

reference_number = PaymentService.authorize(ecommerce_id, auth_token)
```

##### cancel()

Cancel a pending payment.

```python
from django_athm.services import PaymentService

PaymentService.cancel(ecommerce_id)
```

##### refund()

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

Raises `ValueError` if the payment is not refundable or amount exceeds refundable amount.

##### sync_status()

Check remote status and update local payment if necessary.

```python
from django_athm.services import PaymentService
from django_athm.models import Payment

payment = Payment.objects.get(ecommerce_id=uuid)
current_status = PaymentService.sync_status(payment)
```

---

## Constants

Available from `django_athm.constants`:

### Button Theme

```python
from django_athm.constants import BUTTON_COLOR_DEFAULT

BUTTON_COLOR_DEFAULT  # "btn"
```

### Button Languages

```python
from django_athm.constants import (
    BUTTON_LANGUAGE_SPANISH,  # "es"
    BUTTON_LANGUAGE_ENGLISH,  # "en"
)
```
