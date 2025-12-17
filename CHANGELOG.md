# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2025-12-17

First stable release. Complete architectural rewrite from v0.7.0.

### Highlights

- **Webhook-driven synchronization**: Idempotent processing with SHA-256 keys and ACID guarantees
- **Payment lifecycle signals**: `payment_completed`, `payment_cancelled`, `payment_expired`, `refund_sent`
- **Transaction reconciliation**: `athm_sync` command syncs with ATH Movil Transaction Report API
- **Client tracking**: Automatic customer records linked by phone number
- **Read-only Django Admin**: Full audit trails with refund actions and webhook management
- **Optional payment UI**: Zero-dependency JavaScript modal via `athm_button` template tag

### Changed

- Documentation restructured for brevity and usability
- Added feedback issue template

## [1.0.0-beta2] - 2025-12-16

### Added

- **`athm_sync` management command**: Reconcile local Payment records with ATH Movil Transaction Report API
  - `--from-date` and `--to-date` for date range filtering
  - `--dry-run` to preview changes without modifying database
- **`Client` model**: Track customers by normalized phone number
  - Automatic linking from Payment and Refund via `client` ForeignKey
  - Name/email updated from latest webhook events
- **Transaction Report API integration**: `PaymentService.fetch_transaction_report()` method
- **`ClientService`**: Extracted client management logic for reuse

### Changed (BREAKING)

- **Renamed timestamp fields** on all models:
  - `created` -> `created_at`
  - `modified` -> `updated_at`
- **Removed `PaymentLineItem` model**: Line items are no longer persisted locally (sent to API but not stored)
- **Added `client` ForeignKey** to `Payment` and `Refund` models (nullable, SET_NULL on delete)

### Changed

- **Button template rewrite**: Complete overhaul with CSS custom properties for theming (btn, btn-dark, btn-light), improved modal UX
- **Admin enhancements**: Client links, webhooks timeline in Payment detail, reprocess confirmation page, improved search fields
- **Logging**: Switched from f-string to format-style logging throughout services

### Fixed

- Release workflow accepts tags without `v` prefix
- Fixed incorrect URL in release workflow

## [1.0.0-beta1] - 2025-12-09

This is a complete architectural rewrite of django-athm, transitioning from a frontend JavaScript SDK approach to a backend-first webhook-driven payment synchronization system.

**BREAKING CHANGE**: No migration path from v0.7.0. Users must uninstall v0.7.0 completely and freshly integrate v1.0.0-beta1.

### Architecture Shift

**From**: Frontend JavaScript SDK with callback handling
**To**: Backend-first webhook-driven synchronization as the core feature, with an optional payment UI template tag

The library's primary purpose is now **webhook-driven Payment and Refund synchronization** with idempotency and ACID guarantees. The payment modal UI is provided as an optional convenience feature for quick integration.

### Added

#### Webhook Infrastructure (Core Feature)
- **Idempotent webhook processing** with SHA-256 based idempotency keys
  - eCommerce events: `sha256(ecommerceId:status)`
  - Refunds: `sha256(refund:referenceNumber)`
  - Others: `sha256(transactionType:referenceNumber)`
- **ACID transaction guarantees** for payment/refund synchronization
- **WebhookEvent model** for complete audit trails of all webhook events
- **Custom webhook view support** via `process_webhook_request()` function for wrapping webhook handler with custom pre/post-processing logic
- **Webhook URL auto-detection** in admin interface from current request
- **`install_webhook` management command** with optional URL argument and `DJANGO_ATHM_WEBHOOK_URL` setting fallback

#### Payment Lifecycle Signals (Webhook-Triggered)
- `payment_completed` - Fired when eCommerce payment completed webhook received
- `payment_cancelled` - Fired when eCommerce payment cancelled webhook received
- `payment_expired` - Fired when eCommerce payment expired webhook received
- `refund_sent` - Fired when refund sent webhook received

All signals are webhook-triggered and aligned with ATH Móvil event names.

#### Optional Payment UI
- **Backend-first modal** with zero-dependency vanilla JavaScript
- Complete payment flow: `POST /api/initiate/` → poll `GET /api/status/` → `POST /api/authorize/`
- Fully self-contained `athm_button` template tag for quick integration
- Users can build their own payment UI and use only webhook synchronization

#### Developer Experience
- **Read-only Django admin interface** with refund actions and webhook management
- **Multilingual support** (Spanish/English) via Django i18n
- **New models**: `Refund`, `WebhookEvent`
- **Explicit db_table names**: `athm_payment`, `athm_payment_item`, `athm_refund`, `athm_webhook_event`

### Changed (BREAKING)

#### Models
- **ATHM_Transaction → Payment**
  - Primary key: `ecommerce_id` (UUID) instead of auto-increment
  - Status constants: `OPEN`, `CONFIRM`, `COMPLETED`, `CANCEL`, `EXPIRED`
  - FloatField → DecimalField for monetary precision
- **ATHM_Item → PaymentLineItem**
- **Database table names**: All tables use explicit `athm_` prefix

#### API Endpoints
- `/callback/` → `/webhook/` (POST only, idempotent)
- New endpoints: `/api/initiate/`, `/api/status/`, `/api/authorize/`, `/api/cancel/`

#### Dependencies
- **Added**: `athm-python ~0.4.0` for ATH Móvil API client and webhook parsing
- **Django**: 5.1+ required (dropped 4.2)
- **Python**: 3.10-3.13 (dropped 3.8-3.9)

#### Admin Interface
- All models are read-only (no add/change/delete permissions)
- Refund action available on Payment admin
- Webhook management actions in WebhookEvent admin

### Removed

- **Frontend JavaScript SDK integration** - No longer uses ATH Móvil's client-side SDK
- **Legacy `/callback/` endpoint** - Replaced by `/webhook/`
- **`DJANGO_ATHM_CALLBACK_VIEW` setting** - No longer supports custom callback views
- **All backwards compatibility code** from previous versions

### Migration Notes

**No migration path provided.** This is a clean break from v0.7.0.

To upgrade:
1. Uninstall django-athm v0.7.0 completely
2. Remove old migrations and database tables
3. Install django-athm v1.0.0-beta1
4. Run migrations to create new schema
5. Register webhook URL with ATH Móvil using `python manage.py install_webhook`
6. Update application code to use new signals and models
7. Optionally integrate the `athm_button` template tag or build your own payment UI

## [0.7.0] - 2022-08-05

### Added
- Added support for Python 3.10
- Added support for Django versions 4.0 and 4.1
- Added `ATHM_Client` migration missing in `0.6.0`

### Fixed
- Fixed tests due to missing required `date` field for `ATHM_Transactions`.

### Removed
- Removed support for Python versions below 3.8
- Removed support for Django versions below 3.2


## [0.6.0] - 2021-12-04


### Added
- Added `ATHM_Client` model and related logic
- Added `phonenumberslite` package for parsing phone numbers
### Changed
- Change default value for `DJANGO_ATHM_SANDBOX_MODE` setting to `False`
- Upgraded underlying ATH Móvil API
- Added `async` to script tag for ATH Móvil script in base template
- Upgraded jquery in tests folder
### Fixed
- Fix tox in Github Actions
- Fixed `athm_sync` command
- Remove pip cache in Github Actions
## [0.5.0] - 2021-12-04

### Changed
- Update packages
- Update pre-commit config
- Update README and LICENSE
- Use Github CI instead of TravisCI
- Fix deprecation warnings in test
- Use built-in pip caching in actions/setup-python

### Changed

- Update packages
- Add testing for Django 3.2

## [0.4.0] - 2020-11-01

### Changed

- Update packages
- Improved coverage
- Add testing for Django 3.1
- Installed pytest-mock for testing

### Fixed

- Fix model name in documentation

### Removed
- Remove `DummyHTTPAdapter` class


## [0.3.4] - 2020-07-19

### Changed

- Updated packages
- Improved coverage

## [0.3.2] - 2019-02-05

### Added

- Setup tox multi-env testing
- Added classifiers to poetry config

### Changed

- Specify minimum Django version (2.2)
- Cleaned up dev dependencies
- Updated docs

## [0.3.0] - 2019-02-04

### Added

- Sync management command
- Customizable checkout button

## [0.2.0] - 2019-02-03

### Added
- Support [list transactions API](https://github.com/evertec/athMóvil-javascript-api#transactions)

## [0.1.1] - 2019-02-02

### Added

- Django Admin support

## [0.1.0] - 2019-02-02

### Added

- Emit signals upon receiving ATHM response (suggested by @chrisrodz)

### Changed
- `athm_button` template tag no longer takes template context, now requires the configuration options explicitly

- Renamed `ATH_Transaction` and `ATH_Item` models to `ATHM_Transaction` and `ATHM_Item`.

## [0.0.2] - 2019-01-26

### Added

- `athm_button` custom template tag.

## [0.0.1] - 2019-01-26

### Added

- Released PyPI package
