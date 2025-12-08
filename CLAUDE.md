# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`django-athm` is a Django package that integrates ATH M�vil payments (Puerto Rico's mobile payment system) into Django applications. The package provides:

- Payment processing with ATH M�vil's v4 JavaScript API
- Backend-first modal payment flow (v1.0+ architecture)
- Webhook handling for payment events with idempotency
- Transaction persistence with line items
- Django Admin interface for refunds and transaction management
- Management commands for syncing transactions

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

## Architecture

### Payment Flow (v1.0+ Backend-First)

The v1.0 architecture uses a **backend-first modal flow** instead of the legacy JavaScript button:

1. **Initiate** (`/initiate/`): Backend creates payment, returns `ecommerce_id` + `auth_token`
2. **Status Polling** (`/status/`): Frontend polls for payment confirmation (OPEN � CONFIRM)
3. **Authorize** (`/authorize/`): Backend confirms payment with ATH M�vil using `auth_token`
4. **Webhook** (`/webhook/`): ATH M�vil sends completion event with final details (fee, net_amount)

The frontend modal (`button.html`) is a self-contained vanilla JS component with no external dependencies.

### Key Components

**Models** (`django_athm/models.py`):
- `Payment`: Primary transaction record (keyed by `ecommerce_id` UUID from ATH M�vil)
- `PaymentLineItem`: Individual items in a transaction
- `Refund`: Refund records linked to payments
- `WebhookEvent`: Tracks incoming webhook events with idempotency

**Views** (`django_athm/views.py`):
- `initiate`: Creates payment, returns ecommerce_id
- `status`: Polls payment status
- `authorize`: Confirms payment with ATH M�vil
- `cancel`: Cancels pending payment
- `webhook`: Receives ATH M�vil events (idempotent)

**Services**:
- `PaymentService` (`services/payment_service.py`): Orchestrates payment operations
- `WebhookProcessor` (`services/webhook_processor.py`): Handles webhook events with idempotency

**Signals** (`django_athm/signals.py`):
- `payment_created`, `payment_completed`, `payment_failed`, `payment_expired`
- `refund_completed`

### Webhook Idempotency

Webhooks use a deterministic idempotency key based on payload hash to prevent duplicate processing:
- Key format: `{event_type}:{reference_number}:{payload_hash}`
- Database constraint ensures events are only processed once
- ACID guarantees via database-level unique constraints

### Authentication Flow

- `initiate` returns `auth_token` (stored in session)
- `authorize` requires the `auth_token` from session
- Session cleanup after authorization or cancellation

## Configuration

Required settings in Django project:
```python
DJANGO_ATHM_PUBLIC_TOKEN = "your-public-token"
DJANGO_ATHM_PRIVATE_TOKEN = "your-private-token"
DJANGO_ATHM_SANDBOX_MODE = True  # False for production
```

## Template Tag

Use the `athm_button` template tag to render payment buttons:

```django
{% load django_athm %}
{% athm_button ATHM_CONFIG %}
```

Where the view provides `ATHM_CONFIG` dict with keys: `total`, `subtotal`, `tax`, `metadata_1`, `metadata_2`, `items`, `theme`, `lang`.

The button renders a self-contained payment modal with all JavaScript inlined.

## Testing Patterns

- Uses `pytest-django` for tests
- Uses `respx` for mocking HTTPX requests to ATH M�vil API
- Test settings in `tests/settings.py` with sandbox tokens
- Tests run against multiple Django/Python versions via tox

## Dependencies

- **athm-python**: ATH M�vil API client for backend operations
- **Django 5.1+**: Minimum Django version
- **Python 3.10+**: Minimum Python version
- No frontend dependencies (vanilla JavaScript)

## Version Information

Current version targets:
- **v1.0.0-beta**: Webhook-first architecture with backend-first modal flow
- Breaking changes from v0.x (see README migration guide)
- Dropped support for Django <5.1 and Python <3.10
