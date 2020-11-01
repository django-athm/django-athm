# Installation

* Install the package from PyPI.

```bash
pip install django-athm
```

* Add the package to your `INSTALLED_APPS` and configure the needed settings in your `settings.py`.

```python
INSTALLED_APPS = [
    ...,
    "django_athm",
]

DJANGO_ATHM_PUBLIC_TOKEN = 'your-public-token'
DJANGO_ATHM_PRIVATE_TOKEN = 'your-private-token'
```

* Create the model tables for storing ATH Móvil transactions and items.

```bash
python manage.py migrate
```

* Add the default callback function to your root urls:

```python
    urlpatterns = [
        ...,
        path("athm/", include("django_athm.urls", namespace="django_athm")),
    ]
```

* In your views, pass a `ATHM_CONFIG` (or whichever key you prefer) to the context:

```python
def your_view(request):
    context = {
        "ATHM_CONFIG": {
            "theme": "btn",
            "language": "es",
            "total": 25.0,
            "subtotal": 24.0,
            "tax": 1.0,
            "metadata_1": "This is metadata 1",
            "items": [
                {
                    "name": "First Item",
                    "description": "This is a description.",
                    "quantity": "1",
                    "price": "24.00",
                    "tax": "1.00",
                    "metadata": "metadata test",
                }
            ],
        }
    }

    return render(request, "your-template.html", context=context)
```

* In the related templates where you wish to display the Checkout button, load and invoke the `athm_button` custom tag along with your ATHM config from the previous step.

```html
{% load django_athm %} {% athm_button ATHM_CONFIG %}
```

**NOTE**: You must have jQuery loaded in your Django template BEFORE you use the `athm_button` tag.

You can use the following snippet, placing it somewhere above the `athm_button` tag:

```html
<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script>
```

Also, make sure that the CSRF token tag is available in your template. You may need to decorate your views with `@requires_csrf_token`.

* The user clicks on button rendered by your template and then uses the ATH Móvil app to pay the business associated to the public and private tokens you set up in `settings.py`.

* This package will perform a POST `ajax` request on success or failure to the callback view. This will persist the transaction and items in your database.

* You can obtain your transactions and items from the database:

```python
from django_athm.models import ATHM_Transaction, ATHM_Item

my_transactions = ATHM_Transaction.objects.all()
my_items = ATHM_Item.objects.all()
```

* Admin actions are available as well! You can refund transactions directly from the Django Admin interface.

* If you would like to synchronize your database with transactional data from ATH Móvil, you can use the `athm_sync` management command:

```bash
$ python manage.py athm_sync --start "2020-01-01 00:00:00" --end "2020-02-05 12:30:00"
```
