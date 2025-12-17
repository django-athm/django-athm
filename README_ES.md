# django-athm

![Build Status](https://github.com/django-athm/django-athm/actions/workflows/test.yaml/badge.svg)
![readthedocs](https://app.readthedocs.org/projects/django-athm/badge/?version=latest)
[![codecov](https://codecov.io/github/django-athm/django-athm/graph/badge.svg?token=n1uO3iKBPG)](https://codecov.io/github/django-athm/django-athm)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-athm)
![PyPI - Django Version](https://img.shields.io/pypi/djversions/django-athm)
[![PyPI version](https://img.shields.io/pypi/v/django-athm.svg)](https://pypi.org/project/django-athm/)
[![Publicado en Django Packages](https://img.shields.io/badge/Published%20on-Django%20Packages-0c3c26)](https://djangopackages.org/packages/p/django-athm/)
[![Packaged with uv](https://img.shields.io/badge/package_manager-uv-blue.svg)](https://github.com/astral-sh/uv)
![License badge](https://img.shields.io/github/license/django-athm/django-athm.svg)

Integración de Django para pagos con ATH Móvil (principal sistema de pago electrónico en Puerto Rico).

_Ver este README en inglés: [README.md](/README.md)_

## Propósito Principal

**Sincronización de pagos y reembolsos por medio de webhooks**. ATH Móvil envía datos definitivos de transacciones utilizando webhooks, permitiendo tener un record completo de los pagos y reembolsos generados en su cuenta de ATH Móvil Business.

## Características

- **Manejo de webhooks** con idempotencia
- **Persistencia de transacciones** con reembolsos y registros de clientes para auditoría completa
- **Interfaz Django Admin de solo lectura** con acciones de reembolso y configuración de webhooks
- **Django Signals** para eventos del ciclo de vida de pagos (completado, cancelado, expirado, reembolsado)
- **Reconciliación de transacciones** mediante el comando de gestión `athm_sync`
- **Template tag opcional de botón de pago** con JavaScript sin dependencias para integración rápida

## Requisitos

- Python 3.10 - 3.14
- Django 5.1 - 6.0

## Instalación

```bash
pip install django-athm
```

Agregar a `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_athm",
]
```

Agregar tus tokens de la API de ATH Móvil Business (se encuentran en los settings del app móvil):

```python
DJANGO_ATHM_PUBLIC_TOKEN = "your-public-token"
DJANGO_ATHM_PRIVATE_TOKEN = "your-private-token"
```

Incluir URLs:

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    # ...
    path("athm/", include("django_athm.urls")),
]
```

Ejecutar migraciones:

```bash
python manage.py migrate django_athm
```

## Quick Start (con el `templatetag` incluído)

### 1. Crear un view con configuración de pago

```python
# views.py
from django.shortcuts import render

def checkout(request):
    athm_config = {
        "total": 25.00,
        "subtotal": 23.36,
        "tax": 1.64,
        "metadata_1": "orden-123",
        "items": [
            {"name": "Artículo", "price": 23.36, "quantity": 1}
        ],
        "success_url": "/orden/completed/",
        "failure_url": "/orden/failed/",
    }
    return render(request, "checkout.html", {"ATHM_CONFIG": athm_config})
```

### 2. Agregar el botón de pago a tu template

```django
{% load django_athm %}

<h1>Checkout</h1>
{% athm_button ATHM_CONFIG %}
```

### 3. Manejar pago completado mediante Signals

```python
# signals.py
from django.dispatch import receiver
from django_athm.signals import payment_completed

@receiver(payment_completed)
def handle_payment_completed(sender, payment, **kwargs):
    # Actualizar estado de orden, enviar email de confirmación, etc.
    print(f"Pago {payment.reference_number} completado por ${payment.total}")
```

## Arquitectura

### Sincronización Mediante Webhooks

Los webhooks proporcionan datos definitivos de transacciones con garantías de idempotencia:

```
Webhook ATH Móvil -> Procesamiento idempotente -> Sincronización Payment/Refund -> Señales Django
```

### Flujo de Pago con botón (Opcional)

Para integración rápida, usa el template tag incluido:

1. **Iniciar**: Usuario hace clic en el botón, backend crea el pago mediante la API de ATH Móvil
2. **Confirmar**: Usuario confirma el pago en la app de ATH Móvil
3. **Autorizar**: Backend autoriza el pago confirmado
4. **Webhook**: ATH Móvil envía evento de completación con detalles finales

```
Usuario hace clic  ->  Backend crea  ->  Usuario confirma  ->  Backend autoriza  ->  Webhook recibido
en botón ATH Móvil     pago (OPEN)       en app (CONFIRM)      pago (COMPLETED)     (detalles finales)
```

También puedes desarollar tu propia interfaz de pago y usar solamente las características de sincronización mediante webhooks.

## Webhooks

### Instalación de Webhooks

**Recomendado: Usar Django Admin** (detecta automáticamente tu URL de webhook):

1. Navegar a **ATH Móvil Webhook Events** en el admin
2. Hacer clic en el botón **Install Webhooks**
3. Verificar la URL detectada automáticamente (editar si es necesario)
4. Hacer clic en submit para registrar con ATH Móvil

**Alternativa: Comando de gestión**

```bash
# Auto-detectar desde el setting DJANGO_ATHM_WEBHOOK_URL
python manage.py install_webhook

# O proveer URL explícita
python manage.py install_webhook https://example.com/athm/webhook/
```

### Reconciliación de Transacciones

Reconcilia datos locales con la API de Transaction Report de ATH Móvil para recuperar webhooks perdidos o cargar datos historicos:

```bash
# Sincronizar transacciones para un rango de fechas
python manage.py athm_sync --from-date 2025-01-01 --to-date 2025-01-31

# Verificar posibles cambios sin modificar la base de datos
python manage.py athm_sync --dry-run --from-date 2025-01-01 --to-date 2025-01-31
```

### Idempotencia de Webhooks

Todos los webhooks se procesan de manera idempotente usando llaves determinísticas basadas en el payload del evento. Los eventos duplicados se detectan e ignoran automáticamente.

### Lógica custom para los Webhooks

Si necesitas alguna lógica específica antes/después del procesamiento de webhook:

```python
from django.views.decorators.csrf import csrf_exempt
from django_athm.views import process_webhook_request

@csrf_exempt
def mi_webhook_personalizado(request):
    # Pre-procesamiento (logging, rate limiting, etc.)
    log_webhook(request)

    # Llamar al handler de django-athm (mantiene idempotencia)
    response = process_webhook_request(request)

    # Post-procesamiento (notificaciones, analytics, etc.)
    notificar_equipo()

    return response
```

## Django Admin

El paquete proporciona una interfaz admin de solo lectura:

- **Payments**: Ver todas las transacciones, filtrar por estado/fecha, acción de reembolso masivo
- **Refunds**: Ver registros de reembolsos
- **Clients**: Ver registros de clientes vinculados por número de teléfono
- **Webhook Events**: Ver historial de webhooks, reprocesar eventos fallidos, instalar webhooks

Todos los modelos son de solo lectura para preservar la integridad de datos - los pagos solo pueden ser reembolsados, no editados.

## Configuración del Template Tag Opcional

El template tag `athm_button` es **opcional** - puedes construir tu propia interfaz de pago y usar solamente las características de webhooks.

```python
athm_config = {
    # Requerido
    "total": 25.00,              # Monto del pago (1.00 - 1500.00)

    # Opcional
    "subtotal": 23.36,           # Subtotal para mostrar
    "tax": 1.64,                 # Monto de impuestos
    "metadata_1": "orden-123",   # Campo personalizado (máx 40 caracteres)
    "metadata_2": "cliente-456", # Campo personalizado (máx 40 caracteres)
    "items": [...],              # Lista de objetos de articulo
    "theme": "btn",              # Tema del botón: btn, btn-dark, btn-light
    "lang": "es",                # Idioma: es, en
    "success_url": "/gracias/",  # Redirección en éxito (añade ?reference_number=...&ecommerce_id=...)
    "failure_url": "/fallido/",  # Redirección en falla
}
```

## Signals

Suscríbete a eventos del ciclo de vida de pagos:

```python
from django_athm.signals import (
    payment_completed,  # Pago exitoso (webhook)
    payment_cancelled,  # Pago cancelado (webhook)
    payment_expired,    # Pago expirado (webhook)
    refund_sent,        # Reembolso procesado (webhook)
)
```

## Configuración de Desarrollo

Este proyecto usa [uv](https://github.com/astral-sh/uv) para manejar los paquetes.

```bash
# Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar dependencias
uv sync

# Ejecutar pruebas
DJANGO_SETTINGS_MODULE=tests.settings pytest --cov django_athm

# Ejecutar matriz completa de pruebas
tox

# Ejecutar linting
tox -e lint
```

## Legal

Este proyecto **no** está afiliado ni endosado por [Evertec, Inc.](https://www.evertecinc.com/) o [ATH Móvil](https://portal.athMóvil.com/).

## Dependencias

- [athm-python](https://github.com/django-athm/athm-python) - Cliente de API de ATH Móvil

## Referencias

- [Documentación de API de ATH Móvil Business](https://developer.athMóvil.com/)
- [Documentación de los webhooks de ATH Móvil Business](https://github.com/evertec/athMóvil-webhooks)

## Feedback

Tienes sugerencias o ideas para mejorar `django-athm`? Nos encantaría escucharte. [Enviar feedback](https://github.com/django-athm/django-athm/issues/new?template=feedback.yml).

## Licencia

Licencia MIT - ver [LICENSE](LICENSE) para detalles.
