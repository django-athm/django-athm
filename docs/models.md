# Models

All models are in `django_athm.models`.

## Payment

Payment transaction from ATH Móvil.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `ecommerce_id` | UUID | Primary key - ATH Móvil transaction ID |
| `reference_number` | str | Unique reference (populated on completion) |
| `daily_transaction_id` | str | ATH Móvil daily transaction ID |
| `status` | str | Payment status |
| `total` | Decimal | Total amount |
| `subtotal` | Decimal | Subtotal before tax |
| `tax` | Decimal | Tax amount |
| `fee` | Decimal | ATH Móvil processing fee |
| `net_amount` | Decimal | Net amount after fees |
| `total_refunded_amount` | Decimal | Total amount refunded |
| `customer_name` | str | Customer name |
| `customer_phone` | str | Customer phone |
| `customer_email` | str | Customer email |
| `client` | ForeignKey | Associated Client record |
| `metadata_1` | str | Custom metadata (max 40 chars) |
| `metadata_2` | str | Custom metadata (max 40 chars) |
| `message` | str | Optional message |
| `business_name` | str | Business name |
| `transaction_date` | datetime | Transaction completion date |
| `created_at` | datetime | Record creation timestamp |
| `updated_at` | datetime | Last modification timestamp |

### Status Choices

```python
class Status(models.TextChoices):
    OPEN = "OPEN"           # Awaiting customer confirmation
    CONFIRM = "CONFIRM"     # Awaiting authorization
    COMPLETED = "COMPLETED" # Successfully completed
    CANCEL = "CANCEL"       # Cancelled
    EXPIRED = "EXPIRED"     # Expired
```

### Properties

```python
payment.is_successful      # True if COMPLETED
payment.is_refundable      # True if completed with refundable amount
payment.refundable_amount  # Decimal amount available for refund
```

### Query Examples

```python
from django_athm.models import Payment

# Completed payments
Payment.objects.filter(status=Payment.Status.COMPLETED)

# Refundable payments
from django.db.models import F
Payment.objects.filter(
    status=Payment.Status.COMPLETED,
    total__gt=F("total_refunded_amount")
)

# Payment with refunds
payment = Payment.objects.prefetch_related("refunds").get(ecommerce_id=uuid)

# Date range filter
from datetime import datetime
Payment.objects.filter(
    created_at__gte=datetime(2025, 1, 1),
    created_at__lte=datetime(2025, 1, 31)
)
```

## Refund

Refund for a payment.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `payment` | ForeignKey | Related Payment |
| `reference_number` | str | Unique refund reference |
| `daily_transaction_id` | str | ATH Móvil daily transaction ID |
| `amount` | Decimal | Refund amount |
| `message` | str | Refund message (max 50 chars) |
| `status` | str | Status (always "COMPLETED") |
| `customer_name` | str | Customer name |
| `customer_phone` | str | Customer phone |
| `customer_email` | str | Customer email |
| `client` | ForeignKey | Associated Client record |
| `transaction_date` | datetime | Refund transaction date |
| `created_at` | datetime | Record creation timestamp |

### Query Examples

```python
from django_athm.models import Refund

# Refunds for a payment
payment.refunds.all()

# Recent refunds
from datetime import datetime
Refund.objects.filter(created_at__gte=datetime(2025, 1, 1))
```

## WebhookEvent

Webhook event received from ATH Móvil.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `idempotency_key` | str | Unique key for deduplication |
| `event_type` | str | Event type |
| `remote_ip` | str | IP address of webhook request |
| `payload` | JSON | Raw JSON payload |
| `processed` | bool | Whether processed successfully |
| `payment` | ForeignKey | Associated Payment (if any) |
| `refund` | ForeignKey | Associated Refund (if any) |
| `created_at` | datetime | Record creation timestamp |
| `updated_at` | datetime | Last modification timestamp |

### Event Types

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

## Client

Customer record identified by phone number. Automatically created/updated when processing webhooks or syncing transactions.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `phone_number` | str | Unique phone (normalized to digits) |
| `name` | str | Customer name |
| `email` | str | Customer email |
| `created_at` | datetime | Record creation timestamp |
| `updated_at` | datetime | Last modification timestamp |

### Query Examples

```python
from django_athm.models import Client

# Client by phone
client = Client.objects.get(phone_number="7871234567")

# Client's payments and refunds
client.payments.all()
client.refunds.all()

# Repeat customers
from django.db.models import Count
Client.objects.annotate(
    payment_count=Count("payments")
).filter(payment_count__gt=1)
```
