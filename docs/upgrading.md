# Upgrading

## Upgrading to v1.0.0-beta1

Version 1.0.0-beta1 updates django-athm to use ATH Móvil's v4 JavaScript API ([v1.2.3 in this doc](https://github.com/evertec/athMóvil-javascript-api?tab=readme-ov-file#change-log)) with several breaking changes.

### Breaking Changes

#### 1. Sandbox Mode Removed

ATH Móvil's v4 API no longer supports sandbox mode. All transactions are production transactions.

**Before:**
```python
DJANGO_ATHM_SANDBOX_MODE = True  # No longer supported
```

**After:**
Remove `DJANGO_ATHM_SANDBOX_MODE` from your settings. The setting is ignored.

#### 2. Metadata Fields Required

Both `metadata_1` and `metadata_2` are now **required** in your `athm_config`.

**Before:**
```python
"ATHM_CONFIG": {
    "total": 25.00,
    # metadata was optional
}
```

**After:**
```python
"ATHM_CONFIG": {
    "total": 25.00,
    "metadata_1": "Order #12345",      # Required
    "metadata_2": "Customer reference", # Required
}
```

#### 3. phone_number, theme, and language Options Broken

Due to bugs in the ATH Móvil v4 API, these options no longer work:

- **phone_number**: Causes `BTRA_0041` error. The checkout modal will always prompt the customer to enter their phone number. Do not pass this option.
- **theme**: Only `"btn"` works. The `"btn-light"` and `"btn-dark"` options are ignored.
- **language**: Only `"es"` (Spanish) works. The `"en"` (English) option is ignored.

django-athm automatically ignores these values and logs warnings if you provide them. Remove these from your configuration:

**Before:**
```python
"ATHM_CONFIG": {
    "phone_number": customer.phone,  # Remove - causes error
    "theme": "btn-dark",             # Remove - ignored
    "language": "en",                # Remove - ignored
    # ... other fields
}
```

**After:**
```python
"ATHM_CONFIG": {
    # Just remove phone_number, theme, and language
    # ... other fields
}
```

#### 4. Python/Django Version Support

- **Minimum Python**: 3.10
- **Minimum Django**: 5.1

Dropped support for:
- Python 3.9 and earlier
- Django 4.2 and earlier

#### 4a. Server-Side Transaction Verification

The callback view now verifies all transactions with ATH Móvil's API before persisting data. Only `ecommerceId` from the callback POST is trusted; all other transaction data (total, reference_number, status, etc.) is fetched from the API via `find_payment()`.

This change:
- **Prevents spoofed payment data** - Malicious actors can no longer POST fake transaction data
- **Requires valid API credentials** - `DJANGO_ATHM_PUBLIC_TOKEN` and `DJANGO_ATHM_PRIVATE_TOKEN` must be configured
- **Adds new dependency** - [athm-python](https://github.com/django-athm/athm-python) v0.3.0 handles API communication

If verification fails (network error, invalid credentials, etc.), the callback returns HTTP 400 and no transaction is created.

#### 5. Monetary Fields Changed to DecimalField

All monetary fields have been changed from `FloatField` to `DecimalField` for improved precision in financial calculations.

**Affected fields on ATHM_Transaction:**
- `total`
- `subtotal`
- `tax`
- `fee`
- `net_amount`
- `refunded_amount`

**Affected fields on ATHM_Item:**
- `price`
- `tax`

**Impact:** If you have code that expects `float` values, update it to handle `Decimal` values:

```python
from decimal import Decimal

# Before
if transaction.total > 100.0:
    ...

# After
if transaction.total > Decimal("100.00"):
    ...
```

#### 6. New athm_expired_response Signal

A new `athm_expired_response` signal is now dispatched when checkout sessions expire. This allows you to distinguish between explicit user cancellation and session timeout.

```python
from django.dispatch import receiver
from django_athm.signals import athm_expired_response

@receiver(athm_expired_response)
def handle_expired_payment(sender, **kwargs):
    transaction = kwargs.get("transaction")
    # Handle expired session (e.g., notify user, offer retry)
```

### Database Migrations

Run migrations to add new fields to the ATHM_Transaction model:

```bash
python manage.py migrate django_athm
```

New fields added:
- `ecommerce_id` - ATH Móvil eCommerce transaction ID
- `ecommerce_status` - Raw status from ATH Móvil API
- `customer_name` - Customer name from ATH Móvil account
- `customer_phone` - Customer phone from ATH Móvil account
- `net_amount` - Net amount after fees

### New Features

#### QuerySet Methods

New methods for querying transactions:

```python
# Get refunded transactions
ATHM_Transaction.objects.refunded()

# Select related client
ATHM_Transaction.objects.with_client()

# Filter by date range
ATHM_Transaction.objects.by_date_range(start_date, end_date)
```

#### Model Properties

New convenience properties:

```python
transaction.is_refundable  # True if can be refunded
transaction.is_completed   # True if completed
transaction.is_pending     # True if pending
```

#### API Methods

New methods for ATH Móvil v4 API:

```python
# Find a payment by eCommerce ID
ATHM_Transaction.find_payment(ecommerce_id)

# Cancel a pending payment
ATHM_Transaction.cancel_payment(ecommerce_id)
```
