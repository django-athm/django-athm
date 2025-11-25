# django-athm

![Build Status](https://github.com/django-athm/django-athm/actions/workflows/ci.yaml/badge.svg)
[![Codecov status](https://codecov.io/gh/django-athm/django-athm/branch/main/graph/badge.svg)](https://codecov.io/gh/django-athm/django-athm)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-athm)
![PyPI - Django Version](https://img.shields.io/pypi/djversions/django-athm)
[![PyPI version](https://img.shields.io/pypi/v/django-athm.svg)](https://pypi.org/project/django-athm/)
[![Published on Django Packages](https://img.shields.io/badge/Published%20on-Django%20Packages-0c3c26)](https://djangopackages.org/packages/p/django-athm/)
[![Packaged with uv](https://img.shields.io/badge/package_manager-uv-blue.svg)](https://github.com/astral-sh/uv)
![Code style badge](https://badgen.net/badge/code%20style/black/000)
![License badge](https://img.shields.io/github/license/django-athm/django-athm.svg)

_Ver este README en español: [README_ES.md](/README_ES.md)_

## Features

* Persist itemized transaction data as well as client information in your own database.
* The customizable `athm_button` template tag provides convenient access to the ATH Móvil Checkout button.
* Import your existing transactions from ATH Móvil using the `athm_sync` management command.
* Various signals can be used to get notified of completed, cancelled or expired transactions.
* Refund one or more transactions through the Django Admin.


## Migrating from v0.x to v1.0

### Breaking Changes

Version 1.0.0 introduces several breaking changes to align with ATH Móvil's v4 JavaScript API:

#### 1. JavaScript Callback Functions Renamed

If you've customized the payment callbacks, update your function names:

```javascript
// OLD (v0.x) - NO LONGER SUPPORTED
function onCompletedPayment(response) { ... }
function onCancelledPayment(response) { ... }
function onExpiredPayment(response) { ... }

// NEW (v1.0+) - REQUIRED
function authorizationATHM(response) { ... }
function cancelATHM(response) { ... }
function expiredATHM(response) { ... }
```

#### 2. ATH Móvil SDK Source Changed

The JavaScript SDK URL has been updated:

```html
<!-- OLD -->
<script async src="https://www.athmovil.com/api/js/v3/athmovilV3.js"></script>

<!-- NEW -->
<script src="https://payments.athmovil.com/api/js/athmovil_base.js"></script>
```

**Note:** The `async` attribute has been removed - the SDK must load before configuration.

#### 3. Button Container ID Changed

```html
<!-- OLD -->
<div id="ATHMovil_Checkout_Button"></div>

<!-- NEW -->
<div id="ATHMovil_Checkout_Button_payment"></div>
```

#### 4. Django/Python Version Support Updated

- **Minimum Django:** 4.2 LTS (dropped support for 3.2, 4.0, 4.1)
- **Minimum Python:** 3.8
- **Supported Django:** 4.2 LTS, 5.1, 5.2
- **Supported Python:** 3.8-3.13

### New Features in v1.0

- **Phone Number Pre-fill:** Pass `phone_number` in `athm_config` to pre-fill customer phone
- **Enhanced Transaction Tracking:** New fields for `ecommerce_id`, `ecommerce_status`, customer info
- **Automatic Client Creation:** Customer records are now created automatically from transaction data
- **Modern Fetch API:** Replaced jQuery dependency with native fetch API
- **New API Methods:** `find_payment()` and `cancel_payment()` class methods

### Database Migration Required

After upgrading to v1.0.0, run the migration:

```bash
python manage.py migrate django_athm
```

This adds the following fields to `ATHM_Transaction`:
- `ecommerce_id` (indexed)
- `ecommerce_status`
- `customer_name`
- `customer_phone`
- `net_amount`

### Updated Transaction Statuses

New status values:
- `OPEN` - Transaction initiated (new default)
- `CONFIRM` - Transaction confirmed
- `COMPLETED` - Transaction completed successfully
- `CANCEL` - Transaction cancelled
- `REFUNDED` - Transaction refunded

### Example: Updating Your Template

```python
# views.py
athm_config = {
    "total": 100.00,
    "subtotal": 93.00,
    "tax": 7.00,
    "items": items_json,
    # NEW in v1.0: Pre-fill customer phone
    "phone_number": "787-555-1234",
}
```


## Documentation

For information on installation and configuration, see the documentation at:

https://django-athm.github.io/django-athm/

## Development Setup

This project uses [uv](https://github.com/astral-sh/uv) for fast Python package management.

### Installing uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

### Setting up the development environment

```bash
# Create virtual environment
uv venv

# Activate it
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package with development dependencies
uv pip install -e ".[dev]"
```

## Local testing with coverage

After setting up the development environment, you can run the tests:

```bash
DJANGO_SETTINGS_MODULE=tests.settings pytest --cov django_athm
```

### Running the full test matrix with tox

```bash
# Test against all Python and Django versions
tox

# Test specific combination
tox -e py310-django41

# Run linting
tox -e lint
```

## Legal

This project is **not** affiliated with or endorsed by [Evertec, Inc.](https://www.evertecinc.com/) or [ATH Móvil](https://portal.athmovil.com/) in any way.


## Dependencies
* [httpx](https://github.com/encode/httpx/) for performing network requests to the ATH Móvil API
* [phonenumberslite](https://github.com/daviddrysdale/python-phonenumbers) for validating and parsing client phone numbers

## References

- https://github.com/evertec/athmovil-javascript-api

- https://github.com/evertec/athmovil-webhooks

- https://docs.djangoproject.com/en/4.1/ref/csrf/#ajax

- https://docs.djangoproject.com/en/4.1/howto/custom-template-tags/
