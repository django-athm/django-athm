# django-athm 

![CI](https://github.com/django-athm/django-athm/workflows/CI/badge.svg?branch=master)
[![Codecov status](https://codecov.io/gh/django-athm/django-athm/branch/master/graph/badge.svg)](https://codecov.io/gh/django-athm/django-athm)
[![PyPI version](https://img.shields.io/pypi/v/django-athm.svg)](https://pypi.org/project/django-athm/)
[![Packaged with Poetry](https://img.shields.io/badge/package_manager-poetry-blue.svg)](https://poetry.eustace.io/)
![Code style badge](https://badgen.net/badge/code%20style/black/000)
![License badge](https://img.shields.io/github/license/django-athm/django-athm.svg)

_Ver este README en español: [README_ES.md](/README_ES.md)_

## Features

* Persist transactions and item references in your own database.
* Template tag provides convenient access to the ATH Móvil Checkout Button.
* Import your existing transactions from ATH Móvil using the `athm_sync` management command.
* Signals can be used to handle completed, cancelled or expired transactions.
* Refund transactions through the Django Admin.


## Documentation

For information on installation and configuration, see the documentation at:

https://django-athm.github.io/django-athm/

## Legal

This project is not affiliated with or endorsed by [Evertec, Inc.](https://www.evertecinc.com/) or [ATH Móvil](https://portal.athmovil.com/) in any way.


## References

- https://github.com/evertec/athmovil-javascript-api

- https://docs.djangoproject.com/en/3.0/ref/csrf/#ajax

- https://docs.djangoproject.com/en/3.0/howto/custom-template-tags/

