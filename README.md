# django-athm

![Build Status](https://github.com/django-athm/django-athm/actions/workflows/ci.yaml/badge.svg)
[![Codecov status](https://codecov.io/gh/django-athm/django-athm/branch/main/graph/badge.svg)](https://codecov.io/gh/django-athm/django-athm)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-athm)
![PyPI - Django Version](https://img.shields.io/pypi/djversions/django-athm)
[![PyPI version](https://img.shields.io/pypi/v/django-athm.svg)](https://pypi.org/project/django-athm/)
[![Packaged with Poetry](https://img.shields.io/badge/package_manager-poetry-blue.svg)](https://python-poetry.org/)
![Code style badge](https://badgen.net/badge/code%20style/black/000)
![License badge](https://img.shields.io/github/license/django-athm/django-athm.svg)

_Ver este README en español: [README_ES.md](/README_ES.md)_

## Features

* Persist itemized transaction data as well as client information in your own database.
* The customizable `athm_button` template tag provides convenient access to the ATH Móvil Checkout button.
* Import your existing transactions from ATH Móvil using the `athm_sync` management command.
* Various signals can be used to get notified of completed, cancelled or expired transactions.
* Refund one or more transactions through the Django Admin.


## Documentation

For information on installation and configuration, see the documentation at:

https://django-athm.github.io/django-athm/

## Local testing with coverage

Assuming you've already installed all the packages, you can run the following command in the project root folder:

```bash
DJANGO_SETTINGS_MODULE=tests.settings pytest --cov django_athm
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

