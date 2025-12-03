# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

django-athm is a Django integration for ATH Movil, Puerto Rico's mobile payment platform. It provides:
- Database persistence for transactions, items, and clients
- Template tags for rendering the ATH Movil checkout button
- Django signals for payment events (completed, cancelled)
- Management commands for syncing transactions from ATH Movil
- Admin interface for viewing and refunding transactions

## Development Commands

```bash
# Install dependencies (uses uv)
uv pip install -e ".[dev]"

# Run tests with coverage
DJANGO_SETTINGS_MODULE=tests.settings pytest --cov django_athm

# Run a single test file
DJANGO_SETTINGS_MODULE=tests.settings pytest tests/test_models.py

# Run a single test
DJANGO_SETTINGS_MODULE=tests.settings pytest tests/test_models.py::test_function_name -v

# Run full test matrix (all Python/Django versions)
tox

# Run specific tox environment
tox -e py310-django42

# Linting (uses ruff via pre-commit)
pre-commit run --all-files
```

## Architecture

### Core Models (`django_athm/models.py`)
- `ATHM_Client`: Customer records with phone validation
- `ATHM_Transaction`: Payment transactions with status tracking, API methods (`refund`, `search`, `find_payment`, `cancel_payment`)
- `ATHM_Item`: Line items attached to transactions

Custom managers provide filtered querysets: `.completed()`, `.refundable()`, `.pending()`, `.with_items()`

### API Integration
- HTTP requests via `SyncHTTPAdapter` in `utils.py` (uses httpx)
- API endpoints defined in `constants.py`
- Settings loaded from Django settings via `conf.py` (`DJANGO_ATHM_PUBLIC_TOKEN`, `DJANGO_ATHM_PRIVATE_TOKEN`)

### Views (`django_athm/views.py`)
- `default_callback`: POST endpoint receiving payment data from ATH Movil JS SDK
- Creates transactions, items, and clients atomically

### Signals (`django_athm/signals.py`)
- `athm_response_received`: General signal for any response
- `athm_completed_response`, `athm_cancelled_response`: Status-specific

### Template Tags (`django_athm/templatetags/django_athm.py`)
- `athm_button`: Renders the ATH Movil checkout button with configuration

## Testing

Tests use pytest-django with respx for mocking HTTP requests. Test settings in `tests/settings.py`. Fixtures in `tests/conftest.py` provide mocked HTTP adapters.

Coverage requirement: 90% minimum (enforced by tox).

## Commit Convention

Uses commitizen with conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
