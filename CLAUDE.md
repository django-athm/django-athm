# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`django-athm` is a Django package that integrates ATH Movil payments (Puerto Rico's mobile payment system) into Django applications. The package provides:

- Backend-first modal payment flow with ATH Movil's eCommerce API
- Webhook handling for payment events with idempotency and ACID guarantees
- Transaction persistence with line items and refunds
- Read-only Django Admin interface with refund actions and webhook management
- Django signals for payment lifecycle events

## Development Commands

### Setup
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install package with dev dependencies (creates venv automatically)
uv sync
```

### Testing
```bash
# Run tests with coverage
DJANGO_SETTINGS_MODULE=tests.settings pytest --cov django_athm

# Run full test matrix (all Python/Django versions)
tox

# Run specific test environment
tox -e py310-django51

# Run linting
tox -e lint
```

### Code Quality
```bash
# Run ruff linter
ruff check .

# Run ruff formatter
ruff format .

# Check formatting without making changes
ruff format --check .
```

### Management Commands
```bash
# Register webhook URL with ATH Movil
python manage.py install_webhook https://yourdomain.com/athm/webhook/
```

## Architecture

### Payment Flow (Backend-First Modal)

The v1.0 architecture uses a **backend-first modal flow**:

1. **Initiate** (`/api/initiate/`): Backend creates payment via ATH Movil API, returns `ecommerce_id`. Stores `auth_token` in session.
2. **Customer Confirmation**: Customer confirms in ATH Movil app. Status changes OPEN -> CONFIRM.
3. **Status Polling** (`/api/status/`): Frontend should poll until status is CONFIRM.
4. **Authorize** (`/api/authorize/`): Backend confirms payment using session `auth_token`. Returns `reference_number`.
5. **Webhook** (`/webhook/`): ATH Movil sends completion event with final details (fee, net_amount, customer info).

The frontend modal (`button.html`) is self-contained vanilla JS with no external dependencies.

### URL Endpoints

All endpoints are namespaced under `django_athm:`:
- `POST /webhook/` - Receives ATH Movil webhook events
- `POST /api/initiate/` - Creates new payment
- `GET /api/status/` - Polls payment status
- `POST /api/authorize/` - Confirms payment with auth_token
- `POST /api/cancel/` - Cancels pending payment

### Key Components

**Models** (`django_athm/models.py`):
- `Payment`: Primary transaction record (PK: `ecommerce_id` UUID)
- `PaymentLineItem`: Individual items in a transaction
- `Refund`: Refund records linked to payments
- `WebhookEvent`: Tracks webhook events with idempotency

**Views** (`django_athm/views.py`):
- `initiate`, `status`, `authorize`, `cancel`: Payment flow endpoints
- `webhook`: Idempotent webhook receiver

**Services** (`django_athm/services/`):
- `PaymentService`: Orchestrates payment operations via athm-python client
- `WebhookProcessor`: Handles webhook events with idempotency and ACID guarantees

**Admin** (`django_athm/admin.py`):
- All models are read-only (no add/change/delete)
- `PaymentAdmin`: View transactions, bulk refund action
- `WebhookEventAdmin`: View/reprocess webhooks, install webhook URL
- `RefundAdmin`: View refund records

**Signals** (`django_athm/signals.py`):
- `payment_created`: Fired after Payment record created
- `payment_completed`: Fired after payment confirmed via webhook
- `payment_failed`: Fired when payment cancelled
- `payment_expired`: Fired when payment expires
- `refund_completed`: Fired after successful refund

### Webhook Idempotency

Webhooks use deterministic idempotency keys to prevent duplicate processing:
- eCommerce events: `sha256(ecommerceId:status)`
- Refunds: `sha256(refund:referenceNumber)`
- Others: `sha256(transactionType:referenceNumber)`

Database unique constraint on `idempotency_key` ensures events are processed exactly once.

### Payment Statuses

- `OPEN` - Payment initiated, awaiting customer confirmation
- `CONFIRM` - Customer confirmed, awaiting merchant authorization
- `COMPLETED` - Payment authorized and complete
- `CANCEL` - Payment cancelled
- `EXPIRED` - Payment expired (customer didn't confirm in time)

## Configuration

Required settings in Django project:
```python
DJANGO_ATHM_PUBLIC_TOKEN = "your-public-token"
DJANGO_ATHM_PRIVATE_TOKEN = "your-private-token"
```

## Template Tag

Use the `athm_button` template tag to render payment buttons:

```django
{% load django_athm %}
{% athm_button ATHM_CONFIG %}
```

Config dict keys:
- `total` (required): Payment amount (1.00-1500.00)
- `subtotal`: Optional subtotal for display
- `tax`: Optional tax amount
- `metadata_1`, `metadata_2`: Custom fields (max 40 chars)
- `items`: List of item dicts
- `theme`: Button theme (btn, btn-dark, btn-light)
- `lang`: Language code (es, en)
- `success_url`: Redirect URL on success (query params `reference_number` and `ecommerce_id` appended)
- `failure_url`: Redirect URL on failure

## Testing Patterns

- Uses `pytest-django` with fixtures in `tests/`
- Uses `respx` for mocking HTTPX requests to ATH Movil API
- Test settings in `tests/settings.py`
- Tests run against Django 5.1/5.2 and Python 3.10-3.13 via tox

## Dependencies

- **athm-python ~0.4.0**: ATH Movil API client
- **Django 5.1+**: Minimum Django version
- **Python 3.10+**: Minimum Python version

## Database Tables

All tables use explicit `db_table` names:
- `athm_payment`
- `athm_payment_item`
- `athm_refund`
- `athm_webhook_event`
