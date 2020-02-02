# Installation

1. Install the package from PyPI.

```bash
pip install django-athm
```

2. Add the package to your `INSTALLED_APPS` and configure the needed settings in your `settings.py`.

```python
INSTALLED_APPS = [
    ...,
    "django_athm",
]

DJANGO_ATHM_PUBLIC_TOKEN = 'your-public-token'
DJANGO_ATHM_PRIVATE_TOKEN = 'your-private-token'
```

3. _(Optional)_ Create the model tables for storing ATH Móvil transactions and items.

```bash
python manage.py migrate
```

4. Add the default callback function to your root urls (custom callback support coming soon):

```python
    urlpatterns = [
        ...,
        path("athm/", include("django_athm.urls", namespace="django_athm")),
    ]
```

5. In your views, pass a `ATHM_CONFIG` (or whichever key you prefer) to the context:

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

6. In the related templates where you wish to display the Checkout button, load and invoke the `athm_button` custom tag along with your ATHM config from the previous step.

```html
{% load django_athm %}

{% athm_button ATHM_CONFIG %}
```

**NOTE**: You must have jQuery loaded in your Django template BEFORE you use the `athm_button` tag.

You can use the following snippet, placing it somewhere above the `athm_button` tag:
```html
<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script>
```

Also, make sure that the CSRF token tag is available in your template. You may need to decorate your views with `@requires_csrf_token`.

7. The user clicks on button rendered by your template and then uses the ATH Móvil app to pay the business associated to the public and private tokens you set up in `settings.py`.

8. This package will perform a POST `ajax` request on success or failure to the callback view. By default, this will persist the transaction and items in your database.

9. You can obtain your transactions and items from the database:

```python
from django_athm.models import ATHM_Transaction, ATHM_Items

my_transactions = ATHM_Transaction.objects.all()
my_items = ATHM_Items.objects.all()
```
