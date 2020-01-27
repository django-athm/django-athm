# django-athm 

![CI](https://github.com/django-athm/django-athm/workflows/CI/badge.svg?branch=master)
[![codecov](https://codecov.io/gh/django-athm/django-athm/branch/master/graph/badge.svg)](https://codecov.io/gh/django-athm/django-athm)
[![pypi version](https://img.shields.io/pypi/v/django-athm.svg)](https://pypi.org/project/django-athm/)
[![Packaged with poetry](https://img.shields.io/badge/package_manager-poetry-blue.svg)](https://poetry.eustace.io/)
![code style badge](https://badgen.net/badge/code%20style/black/000)
![license badge](https://img.shields.io/github/license/django-athm/django-athm.svg)

Django + ATH Móvil proof-of-concept

## How To Use

1. Install the package.

```bash
pip install django-athm
```

2. Add the package to your `INSTALLED_APPS` and configure the needed settings.

```python
INSTALLED_APPS = [
    ...,
    "django_athm",
]

DJANGO_ATHM_PUBLIC_TOKEN = 'your-public-token'
DJANGO_ATHM_PRIVATE_TOKEN = 'your-private-token'
```

3. Create the model tables for storing ATH Móvil transactions and items.

```bash
python manage.py migrate
```

4. Add the default callback function to your root urls (custom callback support coming soon):

```python
    urlpatterns = [
        ...
        path("athm/", include("django_athm.urls", namespace="django_athm")),
    ]
```

5. In the templates where you wish to display the Checkout button, load and invoke the `athm_button` custom tag.

```html
{% load django_athm %}

{% athm_button %}
```

**NOTE**: You must have jQuery loaded in your Django template BEFORE you use the `athm_button` tag.

You can use the following snippet, placing it somewhere above the `athm_button` tag:
```html
<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script>
```

Also, make sure that the CSRF token is available in your template. You may need to decorate your route with `@requires_csrf_token`.

6. In the related views, pass the `ATHM_CONFIG` to the context:

```python
def your_view(request):
    context = {
        "ATHM_CONFIG": {
            "total": 25.0,
            "subtotal": 24.0,
            "tax": 1.0,
            "items": [
                {
                    "name": "First Item",
                    "description": "This is a description.",
                    "quantity": "1",
                    "price": "24.00",
                    "tax": "1.00",
                    "metadata": "metadata test"
                }
            ]
        }
    }

    return render(request, "your-template.html", context=context)
```

7. The user clicks on button rendered by your template and then uses the ATH Móvil app to pay the business associated to the public and private tokens you set up in `settings.py`.

8. This package will perform a POST `ajax` request on success or failure to the callback view. By default, this will persist the transaction and items in your database.

9. You can obtain your transactions and items from the database:

```python
from django_athm.models import ATH_Transaction, ATH_Items

my_transactions = ATH_Transaction.objects.all()
my_items = ATH_Items.objects.all()
```

## Legal

This project is not affiliated with or endorsed by [Evertec, Inc.](https://www.evertecinc.com/) or [ATH Móvil](https://portal.athmovil.com/) in any way.


## References

- https://github.com/evertec/athmovil-javascript-api

- https://docs.djangoproject.com/en/3.0/ref/csrf/#ajax

- https://docs.djangoproject.com/en/3.0/howto/custom-template-tags/

