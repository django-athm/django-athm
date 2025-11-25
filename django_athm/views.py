import json
import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django_athm import models
from django_athm.signals import (
    athm_cancelled_response,
    athm_completed_response,
    athm_response_received,
)

logger = logging.getLogger(__name__)

app_name = "django_athm"


@csrf_exempt
@require_POST
@transaction.atomic
def default_callback(request):
    """
    Handle ATH Móvil payment callback with comprehensive error handling
    and transaction atomicity.
    """
    try:
        # Extract required fields with validation
        try:
            reference_number = request.POST["referenceNumber"]
            total = float(request.POST["total"])
        except KeyError as e:
            logger.error(
                "[django_athm:missing_required_field]",
                extra={"field": str(e), "post_data": dict(request.POST)},
            )
            return JsonResponse({"error": f"Missing required field: {e}"}, status=400)
        except (ValueError, TypeError) as e:
            logger.error(
                "[django_athm:invalid_field_value]",
                extra={"error": str(e), "post_data": dict(request.POST)},
            )
            return JsonResponse({"error": "Invalid field value format"}, status=400)

        # Extract optional numeric fields with error handling
        def safe_float(value):
            """Safely convert to float, return None if empty/invalid."""
            if not value:
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        subtotal = safe_float(request.POST.get("subtotal"))
        tax = safe_float(request.POST.get("tax"))
        fee = safe_float(request.POST.get("fee"))
        net_amount = safe_float(request.POST.get("netAmount"))

        # Extract metadata fields
        metadata_1 = request.POST.get("metadata1") or None
        metadata_2 = request.POST.get("metadata2") or None

        # Extract v4 API fields
        ecommerce_id = request.POST.get("ecommerceId", "")
        ecommerce_status = request.POST.get("ecommerceStatus", "")
        customer_name = request.POST.get("customerName", "")
        customer_phone = request.POST.get("customerPhone", "")
        customer_email = request.POST.get("customerEmail", "")

        # Create or update client from customer info
        client = None
        if customer_phone:
            try:
                client, created = models.ATHM_Client.objects.get_or_create(
                    phone_number=customer_phone,
                    defaults={
                        "name": customer_name or "Unknown",
                        "email": customer_email or "",
                    },
                )
                # Update name/email if client already exists but has different info
                if not created and customer_name:
                    if client.name != customer_name or (
                        customer_email and client.email != customer_email
                    ):
                        client.name = customer_name
                        if customer_email:
                            client.email = customer_email
                        client.save()
            except ValidationError as e:
                logger.warning(
                    "[django_athm:invalid_phone]",
                    extra={"phone": customer_phone, "error": str(e)},
                )
                # Continue without client if phone validation fails
                client = None

        # Map ecommerce status to internal status
        internal_status = models.ATHM_Transaction.Status.COMPLETED
        if ecommerce_status:
            status_mapping = {
                "COMPLETED": models.ATHM_Transaction.Status.COMPLETED,
                "CANCEL": models.ATHM_Transaction.Status.CANCEL,
                "CANCELLED": models.ATHM_Transaction.Status.CANCEL,
                "OPEN": models.ATHM_Transaction.Status.OPEN,
                "CONFIRM": models.ATHM_Transaction.Status.CONFIRM,
                "REFUNDED": models.ATHM_Transaction.Status.REFUNDED,
            }
            internal_status = status_mapping.get(
                ecommerce_status, models.ATHM_Transaction.Status.COMPLETED
            )

        # Create transaction
        transaction_obj = models.ATHM_Transaction.objects.create(
            reference_number=reference_number,
            status=internal_status,
            total=total,
            subtotal=subtotal,
            tax=tax,
            fee=fee,
            metadata_1=metadata_1,
            metadata_2=metadata_2,
            ecommerce_id=ecommerce_id,
            ecommerce_status=ecommerce_status,
            customer_name=customer_name,
            customer_phone=customer_phone,
            net_amount=net_amount,
            client=client,
            date=timezone.now(),
        )

        logger.info(
            "[django_athm:transaction_created]",
            extra={
                "transaction_id": str(transaction_obj.id),
                "reference_number": reference_number,
                "total": total,
                "status": internal_status,
            },
        )

        # Dispatch signals for payment events
        athm_response_received.send(
            sender=models.ATHM_Transaction,
            transaction=transaction_obj,
        )

        # Dispatch status-specific signals
        if internal_status == models.ATHM_Transaction.Status.COMPLETED:
            athm_completed_response.send(
                sender=models.ATHM_Transaction,
                transaction=transaction_obj,
            )
        elif internal_status == models.ATHM_Transaction.Status.CANCEL:
            athm_cancelled_response.send(
                sender=models.ATHM_Transaction,
                transaction=transaction_obj,
            )

        # Parse and create items with error handling
        items_data = request.POST.get("items", "[]")
        try:
            items = json.loads(items_data)
        except json.JSONDecodeError as e:
            logger.error(
                "[django_athm:invalid_items_json]",
                extra={"error": str(e), "items_data": items_data},
            )
            # Continue without items if JSON is invalid
            items = []

        item_instances = []
        for item in items:
            try:
                item_instances.append(
                    models.ATHM_Item(
                        transaction=transaction_obj,
                        name=item.get("name", "")[:32],  # Enforce max length
                        description=item.get("description", "")[:128],
                        quantity=int(item.get("quantity", 1)),
                        price=float(item.get("price", 0)),
                        tax=safe_float(item.get("tax")),
                        metadata=item.get("metadata") or None,
                    )
                )
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(
                    "[django_athm:invalid_item]",
                    extra={"error": str(e), "item": item},
                )
                # Skip invalid items but continue processing

        if item_instances:
            models.ATHM_Item.objects.bulk_create(item_instances)
            logger.debug(
                "[django_athm:items_created]",
                extra={
                    "transaction_id": str(transaction_obj.id),
                    "item_count": len(item_instances),
                },
            )

        return HttpResponse(status=201)

    except Exception as e:
        logger.exception(
            "[django_athm:callback_error]",
            extra={"error": str(e), "post_data": dict(request.POST)},
        )
        return JsonResponse(
            {"error": "Internal server error processing payment callback"},
            status=500,
        )
