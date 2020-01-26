# django-athm

Django + ATH Móvil proof-of-concept

References

- https://github.com/evertec/athmovil-javascript-api

- https://docs.djangoproject.com/en/3.0/ref/csrf/#ajax

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

4.

```python
    urlpatterns = [
        ...
        path("athm/", include("django_athm.urls", namespace="django_athm")),
    ]
```

5. In the templates where you wish to display the Checkout button, load and invoke the `athm_button` tag.

```html
{% load django_athm %}

{% athm_button ATHM_CONFIG %}
```

**NOTE**: You must have jQuery loaded in your Django template BEFORE you use the `athm_button` tag.

You can use the following snippet, placing it somewhere above the `athm_button` tag:
```html
<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script>
```

6. In the related views, pass the `ATHM_CONFIG` to the context:

```python
def your_view(request):
    context = {
        "ATHM_CONFIG": {
            "env": "production",
            "public_token": settings.DJANGO_ATHM_PUBLIC_TOKEN,
            "lang": "en",
            "total": 25.00,
            "items": [
                {
                    "name": "First Item",
                    "description": "This is a description.",
                    "quantity": "1",
                    "price": "24.00",
                    "tax": "1.00",
                    "metadata": "metadata test",
                },
            ],
        }
    }
    return render(request, "your-template.html", context=context)
```

7. The user clicks on button rendered by your template and then uses the ATH Móvil app to pay the business associated to the public and private tokens you set up in `settings.py`.

8. This package will perform an `ajax` request on success or failure to the URL that resolves for `athm_callback`. By default, this will be a simple view that will create the transaction and related items.

9. You can obtain your transactions and items from the database:

```python
from django_athm.models import ATH_Transaction, ATH_Items

my_transactions = ATH_Transaction.objects.all()
my_items = ATH_Items.objects.all()
```

