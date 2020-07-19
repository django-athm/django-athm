# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Allow usage of custom Transaction model
- Allow usage of custom callback View
- Strict data validation in template and callback view
- Async support
    - Django 3 support
    - httpx async
- 100% test coverage

## [0.3.4] - 2020-07-19

## Changed

- Updated packages
- Improved coverage

## [0.3.2] - 2019-02-05

## Added

- Setup tox multi-env testing
- Added classifiers to poetry config

## Changed

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
