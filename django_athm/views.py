import json
import logging

from django.http import HttpResponse
from django.utils import timezone

from django_athm import models

logger = logging.getLogger(__name__)

app_name = "django_athm"


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

    transaction = models.ATHM_Transaction.objects.create(
        reference_number=reference_number,
        status=models.ATHM_Transaction.Status.COMPLETED,
        total=total,
        subtotal=subtotal,
        tax=tax,
        metadata_1=metadata_1,
        metadata_2=metadata_2,
        date=timezone.now(),
    )

    item_instances = []
    items = json.loads(request.POST["items"])

    for item in items:
        item_instances.append(
            models.ATHM_Item(
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
        models.ATHM_Item.objects.bulk_create(item_instances)

    # TODO: Create ATHM_Client instance

    return HttpResponse(status=201)
