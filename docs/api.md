# API Reference

## Models

### ATHM_Transaction

Represents a payment transaction from ATH Móvil.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField | Primary key |
| `reference_number` | CharField | Unique ATH Móvil reference number |
| `status` | CharField | Transaction status (see Status choices below) |
| `date` | DateTimeField | Transaction date |
| `total` | DecimalField | Total amount |
| `subtotal` | DecimalField | Subtotal before tax |
| `tax` | DecimalField | Tax amount |
| `fee` | DecimalField | ATH Móvil fee |
| `net_amount` | DecimalField | Net amount after fees |
| `refunded_amount` | DecimalField | Amount refunded (if any) |
| `message` | CharField | Optional message |
| `metadata_1` | CharField | Metadata field 1 (max 40 chars) |
| `metadata_2` | CharField | Metadata field 2 (max 40 chars) |
| `ecommerce_id` | CharField | ATH Móvil eCommerce transaction ID |
| `ecommerce_status` | CharField | Raw status from ATH Móvil API |
| `customer_name` | CharField | Customer name from ATH Móvil |
| `customer_phone` | CharField | Customer phone from ATH Móvil |
| `client` | ForeignKey | Related ATHM_Client |

#### Status Choices

```python
class Status(models.TextChoices):
    OPEN = "open"           # Transaction initiated
    CONFIRM = "confirm"     # Awaiting confirmation
    COMPLETED = "completed" # Successfully completed
    CANCEL = "cancel"       # Cancelled by customer
    REFUNDED = "refunded"   # Refunded
```

#### Properties

```python
transaction.is_refundable  # True if completed and not yet refunded
transaction.is_completed   # True if status is COMPLETED
transaction.is_pending     # True if status is OPEN or CONFIRM
```

#### Class Methods

##### get_report(start_date, end_date, public_token=None, private_token=None)

Fetch a transaction report from ATH Móvil API.

```python
from django_athm.models import ATHM_Transaction

report = ATHM_Transaction.get_report(
    start_date="2025-01-01",
    end_date="2025-01-31"
)
```

##### refund(transaction, amount=None)

Refund a transaction. Defaults to full refund.

```python
from django_athm.models import ATHM_Transaction

transaction = ATHM_Transaction.objects.get(reference_number="abc123")

# Full refund
response = ATHM_Transaction.refund(transaction)

# Partial refund
response = ATHM_Transaction.refund(transaction, amount=10.00)
```

Raises `ATHM_RefundError` if the refund fails.

##### search(transaction)

Search for transaction details from ATH Móvil API.

```python
from django_athm.models import ATHM_Transaction

transaction = ATHM_Transaction.objects.get(reference_number="abc123")
details = ATHM_Transaction.search(transaction)
```

##### find_payment(ecommerce_id, public_token=None)

Find a payment by eCommerce ID using the ATH Móvil v4 API.

```python
from django_athm.models import ATHM_Transaction

result = ATHM_Transaction.find_payment(ecommerce_id="ecom123")
```

##### cancel_payment(ecommerce_id, public_token=None)

Cancel a pending payment using the ATH Móvil v4 API.

```python
from django_athm.models import ATHM_Transaction

result = ATHM_Transaction.cancel_payment(ecommerce_id="ecom123")
```

#### QuerySet Methods

All methods are chainable and available on both `ATHM_Transaction.objects` and QuerySets.

```python
# Get completed transactions
ATHM_Transaction.objects.completed()

# Get transactions that can be refunded
ATHM_Transaction.objects.refundable()

# Get refunded transactions
ATHM_Transaction.objects.refunded()

# Get pending transactions (OPEN or CONFIRM status)
ATHM_Transaction.objects.pending()

# Prefetch related items
ATHM_Transaction.objects.with_items()

# Select related client
ATHM_Transaction.objects.with_client()

# Filter by date range
ATHM_Transaction.objects.by_date_range(start_date, end_date)

# Chain methods
ATHM_Transaction.objects.completed().with_items().by_date_range(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 1, 31)
)
```

---

### ATHM_Client

Represents a customer who has made payments.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField | Primary key |
| `name` | CharField | Customer name |
| `email` | EmailField | Customer email |
| `phone_number` | CharField | Customer phone (validated) |

#### QuerySet Methods

```python
# Get clients with their transactions prefetched
ATHM_Client.objects.with_transactions()
```

---

### ATHM_Item

Represents a line item in a transaction.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField | Primary key |
| `transaction` | ForeignKey | Related ATHM_Transaction |
| `name` | CharField | Item name (max 32 chars) |
| `description` | CharField | Item description (max 128 chars) |
| `quantity` | PositiveSmallIntegerField | Quantity |
| `price` | DecimalField | Price per item |
| `tax` | DecimalField | Tax for this item |
| `metadata` | CharField | Item metadata (max 40 chars) |

---

## Exceptions

All exceptions are available from `django_athm.exceptions`:

```python
from django_athm.exceptions import ATHM_Error, ATHM_RefundError
```

### ATHM_Error

Base exception for all django-athm errors.

### ATHM_RefundError

Raised when a refund operation fails.

```python
from django_athm.exceptions import ATHM_RefundError

try:
    ATHM_Transaction.refund(transaction)
except ATHM_RefundError as e:
    print(f"Refund failed: {e}")
```

---

## Constants

Available from `django_athm.constants`:

### Button Themes

```python
from django_athm.constants import (
    BUTTON_COLOR_DEFAULT,  # "btn"
    BUTTON_COLOR_LIGHT,    # "btn-light"
    BUTTON_COLOR_DARK,     # "btn-dark"
)
```

### Button Languages

```python
from django_athm.constants import (
    BUTTON_LANGUAGE_SPANISH,  # "es"
    BUTTON_LANGUAGE_ENGLISH,  # "en"
)
```

### Transaction Status

```python
from django_athm.constants import TransactionStatus

TransactionStatus.completed   # "COMPLETED"
TransactionStatus.cancelled   # "CANCELLED"
TransactionStatus.expired     # "EXPIRED"
TransactionStatus.refunded    # "REFUNDED"
```
