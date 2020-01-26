import json
import logging

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token

from django_athm import models

logger = logging.getLogger(__name__)

app_name = "django_athm"


@requires_csrf_token
def index(request):
    context = {
        "ATHM_CONFIG": {
            "env": "sandbox",
            "public_token": "sandboxtoken01875617264",
            "lang": "en",
            "total": 25.00,
            "items": [
                {
                    "name": "First Item",
                    "description": "This is a description.",
                    "quantity": "1",
                    "price": "1.00",
                    "tax": "1.00",
                    "metadata": "metadata test",
                },
                {
                    "name": "Second Item",
                    "description": "Hello world",
                    "quantity": "3",
                    "price": "2.00",
                    "tax": "",
                    "metadata": "",
                },
            ],
        }
    }
    return render(request, "button.html", context=context)


def default_callback(request):
    reference_number = request.POST["referenceNumber"]
    total = float(request.POST["total"])

    subtotal = request.POST["subtotal"]
    if subtotal:
        subtotal = float(subtotal)
    else:
        subtotal = None

    tax = request.POST["tax"]
    if tax:
        tax = float(tax)
    else:
        tax = None

    metadata_1 = request.POST["metadata1"]
    if not metadata_1:
        metadata_1 = None

    metadata_2 = request.POST["metadata2"]
    if not metadata_2:
        metadata_2 = None

    transaction = models.ATH_Transaction.objects.create(
        reference_number=reference_number,
        status=models.ATH_Transaction.PROCESSING,
        total=total,
        subtotal=subtotal,
        tax=tax,
        metadata_1=metadata_1,
        metadata_2=metadata_2,
    )

    item_instances = []
    items = json.loads(request.POST["items"])

    for item in items:
        item_instances.append(
            models.ATH_Item(
                transaction=transaction,
                name=item["name"],
                description=item["description"],
                quantity=int(item["quantity"]),
                price=float(item["price"]),
                tax=float(item["tax"]) if item["tax"] else None,
                metadata=item["metadata"] if item["metadata"] else None,
            )
        )

    if item_instances:
        models.ATH_Item.objects.bulk_create(item_instances)

    return HttpResponse()
