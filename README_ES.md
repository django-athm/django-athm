# django-athm

[![Build Status](https://travis-ci.org/django-athm/django-athm.svg?branch=main)](https://travis-ci.org/django-athm/django-athm)
[![Codecov status](https://codecov.io/gh/django-athm/django-athm/branch/main/graph/badge.svg)](https://codecov.io/gh/django-athm/django-athm)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-athm)
![PyPI - Django Version](https://img.shields.io/pypi/djversions/django-athm)
[![PyPI version](https://img.shields.io/pypi/v/django-athm.svg)](https://pypi.org/project/django-athm/)
[![Packaged with Poetry](https://img.shields.io/badge/package_manager-poetry-blue.svg)](https://poetry.eustace.io/)
![Code style badge](https://badgen.net/badge/code%20style/black/000)
![License badge](https://img.shields.io/github/license/django-athm/django-athm.svg)

_See this README in English: [README.md](/README.md)_

## Características

* Persiste referencias a transacciones y artículos en su propia base de datos.
* El template tag `athm_button` es customizable y provee acceso conveniente al botón de ATH Móvil.
* Importe sus transacciones existentes utilizando el comando `athm_sync`.
* Se pueden utilizar Django signals para manejar alertas sobre transacciones completadas, canceladas o expiradas.
* Reembolsa una o más transacciones directamente desde el Django Admin.


## Documentación

Para más información sobre la instalación y configuración, ver la documentación disponible en:

https://django-athm.github.io/django-athm/

## Pruebas locales con cobertura

Asumiendo que ya tienes todos los paquetes instalados, puedes correr el siguiente comando desde el tope del proyecto:

```bash
DJANGO_SETTINGS_MODULE=tests.settings pytest --cov django_athm
```

## Legal

Este proyecto no está afiliado ni endosado de ninguna manera por [Evertec, Inc.](https://www.evertecinc.com/) ni [ATH Móvil](https://portal.athmovil.com/).


## Referencias

- https://github.com/evertec/athmovil-javascript-api

- https://docs.djangoproject.com/en/3.0/ref/csrf/#ajax

- https://docs.djangoproject.com/en/3.0/howto/custom-template-tags/

