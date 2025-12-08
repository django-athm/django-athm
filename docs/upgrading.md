# Upgrading

## Upgrading to v1.0

Version 1.0 is a complete rewrite of django-athm with a new backend-first modal architecture. This guide covers migrating from earlier versions.

### Breaking Changes

#### 1. Model Renames

All models have been renamed:

| Old Name | New Name |
|----------|----------|
| `ATHM_Transaction` | `Payment` |
| `ATHM_Item` | `PaymentLineItem` |
| `ATHM_Client` | Removed (customer fields now on `Payment`) |

**Migration:**

```python
# Before
from django_athm.models import ATHM_Transaction, ATHM_Item

# After
from django_athm.models import Payment, PaymentLineItem
```

#### 2. Field Changes

**Payment model:**

| Old Field | New Field |
|-----------|-----------|
| `id` | `ecommerce_id` (now primary key) |
| `date` | `transaction_date` |
| `refunded_amount` | `total_refunded_amount` |
| `client` | Removed (use `customer_name`, `customer_phone`, `customer_email`) |

**Status values are now uppercase:**

```python
# Before
Payment.Status.OPEN = "open"
Payment.Status.COMPLETED = "completed"

# After
Payment.Status.OPEN = "OPEN"
Payment.Status.COMPLETED = "COMPLETED"
```

#### 3. Signal Renames

All signals have been renamed:

| Old Signal | New Signal |
|------------|------------|
| `athm_response_received` | Removed |
| `athm_completed_response` | `payment_completed` |
| `athm_cancelled_response` | `payment_failed` |
| `athm_expired_response` | `payment_expired` |
| - | `payment_created` (new) |
| - | `refund_completed` (new) |

**Signal arguments changed from `transaction=` to `payment=`:**

```python
# Before
@receiver(athm_completed_response)
def handle(sender, **kwargs):
    transaction = kwargs.get("transaction")

# After
@receiver(payment_completed)
def handle(sender, payment, **kwargs):
    # payment is now a direct argument
    pass
```

#### 4. Removed Settings

The following settings no longer exist:

- `DJANGO_ATHM_SANDBOX_MODE` - Sandbox mode removed by ATH Movil
- `DJANGO_ATHM_CALLBACK_VIEW` - Custom callbacks removed (use signals instead)

#### 5. Removed Features

- **Custom callback views**: Use [signals](signals.md) to respond to payment events
- **ATHM_Client model**: Customer info is now stored directly on the `Payment` model
- **QuerySet methods**: Use standard Django ORM queries instead
- **Model class methods**: Use `PaymentService` instead

#### 6. New Architecture

django-athm now uses a backend-first modal flow:

1. Frontend button opens modal and prompts for phone number
2. Backend creates payment via API (`/api/initiate/`)
3. Customer confirms in ATH Movil app
4. Frontend polls for status (`/api/status/`)
5. Backend authorizes payment (`/api/authorize/`)
6. Webhook receives final transaction details

#### 7. New URL Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/` | POST | Receives ATH Movil webhook events |
| `/api/initiate/` | POST | Creates new payment |
| `/api/status/` | GET | Polls payment status |
| `/api/authorize/` | POST | Confirms payment |
| `/api/cancel/` | POST | Cancels pending payment |

#### 8. Python/Django Version Support

- **Minimum Python**: 3.10
- **Minimum Django**: 5.1

Dropped support for:
- Python 3.9 and earlier
- Django 4.2 and earlier

#### 9. Monetary Fields Use DecimalField

All monetary fields use `DecimalField` for precision:

```python
from decimal import Decimal

# Use Decimal for comparisons
if payment.total > Decimal("100.00"):
    ...
```

### Database Migrations

Run migrations to update your database schema:

```bash
python manage.py migrate django_athm
```

### Code Migration Examples

**Querying payments:**

```python
# Before
ATHM_Transaction.objects.completed()
ATHM_Transaction.objects.refundable()

# After
Payment.objects.filter(status=Payment.Status.COMPLETED)
Payment.objects.filter(
    status=Payment.Status.COMPLETED,
    total__gt=models.F("total_refunded_amount")
)
```

**Processing refunds:**

```python
# Before
from django_athm.models import ATHM_Transaction
ATHM_Transaction.refund(transaction, amount=10.00)

# After
from django_athm.services import PaymentService
PaymentService.refund(payment, amount=Decimal("10.00"))
```

**Signal handlers:**

```python
# Before
from django_athm.signals import athm_completed_response

@receiver(athm_completed_response)
def handle(sender, **kwargs):
    transaction = kwargs.get("transaction")
    order = Order.objects.get(ref=transaction.metadata_1)

# After
from django_athm.signals import payment_completed

@receiver(payment_completed)
def handle(sender, payment, **kwargs):
    order = Order.objects.get(ref=payment.metadata_1)
```
