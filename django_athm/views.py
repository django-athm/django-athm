import json
import logging
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone

from django_athm import models

logger = logging.getLogger(__name__)

app_name = "django_athm"


def _parse_decimal(value):
    """Helper to parse decimal values from POST data."""
    return Decimal(value) if value else None


def default_callback(request):
    reference_number = request.POST["referenceNumber"]
    total = Decimal(request.POST["total"])

    subtotal = _parse_decimal(request.POST["subtotal"])
    tax = _parse_decimal(request.POST["tax"])

    metadata_1 = request.POST["metadata1"] or None
    metadata_2 = request.POST["metadata2"] or None

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
                price=Decimal(item["price"]),
                tax=_parse_decimal(item["tax"]),
                metadata=item["metadata"] or None,
            )
        )

    if item_instances:
        models.ATHM_Item.objects.bulk_create(item_instances)

    # TODO: Create ATHM_Client instance

    return HttpResponse(status=201)
