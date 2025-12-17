# Quickstart

Accept your first ATH Móvil payment in minutes using our **optional** payment button template tag.

## Prerequisites

- [Installation](installation.md) complete
- ATH Móvil Business account with API tokens

## 1. Create a Checkout View

```python
# views.py
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token

@requires_csrf_token
def checkout(request):
    context = {
        "ATHM_CONFIG": {
            "total": 25.00,
            "subtotal": 24.00,
            "tax": 1.00,
            "metadata_1": "Order #12345",
            "success_url": "/checkout/success/",
            "failure_url": "/checkout/",
        }
    }
    return render(request, "checkout.html", context)
```

## 2. Create the Template

```html
<!-- templates/checkout.html -->
{% load django_athm %}
<!DOCTYPE html>
<html>
<head>
    <title>Checkout</title>
</head>
<body>
    <h1>Checkout</h1>
    <p>Total: $25.00</p>
    {% athm_button ATHM_CONFIG %}
</body>
</html>
```

## 3. Handle Payment Events

```python
# signals.py
from django.dispatch import receiver
from django_athm.signals import payment_completed

@receiver(payment_completed)
def handle_payment(sender, payment, **kwargs):
    # Update your order status
    print(f"Payment received: {payment.reference_number}")
```

Register the signal handler in your app config:

```python
# apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = "myapp"

    def ready(self):
        import myapp.signals  # noqa: F401
```

## 4. Add URL Routes

```python
# urls.py
from django.urls import include, path
from . import views

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("athm/", include("django_athm.urls")),
]
```

## Payment Flow

1. Customer clicks the ATH Móvil button
2. Modal prompts for phone number
3. Customer receives push notification on ATH Móvil app
4. Customer approves payment
5. Webhook arrives with transaction details
6. `payment_completed` signal fires
7. Customer redirects to `success_url`

## Next Steps

- [Webhooks](webhooks.md) - Install your webhook URL
- [Signals](signals.md) - Handle all payment events
- [Configuration](configuration.md) - Template tag options
