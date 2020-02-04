# django-athm 

![CI](https://github.com/django-athm/django-athm/workflows/CI/badge.svg?branch=master)
[![Codecov status](https://codecov.io/gh/django-athm/django-athm/branch/master/graph/badge.svg)](https://codecov.io/gh/django-athm/django-athm)
[![PyPI version](https://img.shields.io/pypi/v/django-athm.svg)](https://pypi.org/project/django-athm/)
[![Packaged with Poetry](https://img.shields.io/badge/package_manager-poetry-blue.svg)](https://poetry.eustace.io/)
![Code style badge](https://badgen.net/badge/code%20style/black/000)
![License badge](https://img.shields.io/github/license/django-athm/django-athm.svg)

_See this README in English: [README.md](/README.md)_

## Características

* Persiste referencias a transacciones y artículos en tu propia base de datos.
* El template tag provee acceso conveniente al botón de ATH Móvil.
* Importe sus transacciones existentes utilizando el comando `athm_sync`.
* Se pueden utilizar signals para manejar alertas sobre transacciones completadas, canceladas o expiradas.
* Reembolsa transacciones a través del Django Admin.


## Documentación

Para más información sobre la instalación y configuración, ver la documentación disponible en:

https://django-athm.github.io/django-athm/

## Legal

Este proyecto no está afiliado ni endosado de ninguna manera por [Evertec, Inc.](https://www.evertecinc.com/) ni [ATH Móvil](https://portal.athmovil.com/).


## Referencias

- https://github.com/evertec/athmovil-javascript-api

- https://docs.djangoproject.com/en/3.0/ref/csrf/#ajax

- https://docs.djangoproject.com/en/3.0/howto/custom-template-tags/

