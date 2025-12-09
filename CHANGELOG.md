# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0-beta1] - 2025-12-09

This is a complete architectural rewrite of django-athm. The library now uses a backend-first modal payment flow with webhooks instead of the frontend JavaScript SDK approach. **No migration path is provided**; this is a clean break from v0.7.0 which would require

### Added

- **Optional Backend-first, zero-dependency JavaScript powered templatetag** as an optional feature for quick integration (POST /api/initiate/ → poll /api/status/ → POST /api/authorize/)
- **New models**: Refund, WebhookEvent
- **install_webhook management command** for CLI-based webhook URL registration
- **Multilingual support** with Spanish and English translations using Django i18n
- **Django signals system** for payment lifecycle events: payment_created, payment_completed, payment_failed, payment_expired, refund_completed

### Changed (BREAKING)

- **Complete architectural rewrite**: Frontend JavaScript SDK → Backend-first modal with webhooks
- **Model renames**: ATHM_Transaction → Payment, ATHM_Item → PaymentLineItem
- **Database table names**: Explicit athm_ prefixes (athm_payment, athm_payment_item, athm_refund, athm_webhook_event)
- **Signal renames**: All payment lifecycle signals renamed with new signatures
- **Monetary fields**: FloatField → DecimalField for precision
- **Admin actions**: Read-only enforcement on all models, confirmation flows for destructive operations
- **Payment flow**: Backend initiates payment, (optionally) frontend polls status, backend authorizes on customer confirmation
- **Primary key**: Payment uses ecommerce_id (UUID) as primary key instead of auto-increment
- **Status constants**: New enum with OPEN, CONFIRM, COMPLETED, CANCEL, EXPIRED
- **Updated Django support**: Now requires Django 5.1 minimum. Supports Django 5.1, 5.2. Dropped Django 4.2.
- **Updated Python support**: Now requires Python 3.10 minimum. Supports Python 3.10-3.13. Dropped Python 3.8, 3.9.
- **New dependency**: athm-python v0.4.0 for ATH Móvil API communication

### Removed

- **Frontend JavaScript SDK integration** - No longer uses ATH Móvil's client-side SDK
- **Legacy callback view** (/callback/) - Replaced by webhook endpoint
- **DJANGO_ATHM_CALLBACK_VIEW setting** - No longer configurable callback views
- **PROCESSING status** - Use OPEN instead

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
