# Upgrading

## Upgrading to v1.0.0-beta1

Version 1.0.0-beta1 updates django-athm to use ATH Móvil's v4 JavaScript API ([v1.2.3 in this doc](https://github.com/evertec/athmovil-javascript-api?tab=readme-ov-file#change-log)) with several breaking changes.

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

- **Minimum Python**: 3.8
- **Minimum Django**: 4.2

Dropped support for:
- Python 3.7 and earlier
- Django 3.2, 4.0, 4.1

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
