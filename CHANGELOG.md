# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed (BREAKING)

- **Updated to ATH Móvil JavaScript v4 API** - New SDK URL and integration requirements
- **Renamed JavaScript callback functions** to match new API:
  - `onCompletedPayment` → `authorizationATHM`
  - `onCancelledPayment` → `cancelATHM`
  - `onExpiredPayment` → `expiredATHM`
- **Changed button container ID** from `ATHMovil_Checkout_Button` to `ATHMovil_Checkout_Button_payment`
- **Updated Django support:** Now requires Django 4.2 LTS minimum. Supports Django 4.2, 5.1, 5.2
- **Updated Python support:** Dropped Python 3.8 (for Django 5.1+). Supports Python 3.8-3.13
- **Removed jQuery dependency** - Now uses native Fetch API for callback requests
- **Updated transaction status values** - Added `OPEN`, `CONFIRM`, `CANCEL` status choices

### Added

- **Phone number pre-fill support** - Pass `phone_number` in `athm_config` to pre-populate customer phone
- **New transaction fields:**
  - `ecommerce_id` (indexed) - ATH Móvil eCommerce transaction ID
  - `ecommerce_status` - Status from ATH Móvil API
  - `customer_name` - Customer name from ATH Móvil account
  - `customer_phone` - Customer phone from ATH Móvil account
  - `net_amount` - Net amount after fees (changed from computed property to field)
- **Automatic client creation** - ATHM_Client records now created/updated automatically from transaction callbacks
- **New API methods:**
  - `ATHM_Transaction.find_payment()` - Find payment using ATH Móvil v4 API
  - `ATHM_Transaction.cancel_payment()` - Cancel payment using ATH Móvil v4 API
- **New API endpoint constants** for v4 API
- **Django 5.1 and 5.2 support**
- **Python 3.11, 3.12, and 3.13 support**
- Strict data validation in template and callback view

### Fixed

- **Implemented client creation in callback** - Fixed long-standing TODO in `default_callback()` view
- **Version inconsistency** - Synchronized version between `pyproject.toml` and `__init__.py`

### Removed

- **Dropped Django 3.2, 4.0, 4.1 support** - Minimum version now Django 4.2 LTS


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
- Support [list transactions API](https://github.com/evertec/athmovil-javascript-api#transactions)

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
