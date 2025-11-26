import logging
from decimal import Decimal

from athm import ATHMovilClient
from athm.exceptions import ATHMovilError
from django.conf import settings as django_settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.timezone import is_aware, make_aware
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django_athm import models
from django_athm.signals import (
    athm_cancelled_response,
    athm_completed_response,
    athm_expired_response,
    athm_response_received,
)

logger = logging.getLogger(__name__)

app_name = "django_athm"


@csrf_exempt
@require_POST
@transaction.atomic
def default_callback(request):
    """
    Handle ATH Movil payment callback with server-side verification.

    Only the ecommerceId from POST is trusted. All other transaction data
    is fetched from ATH Movil's API via find_payment() for verification.
    """
    try:
        # Check for intermediate statuses (OPEN, CONFIRM) - return early
        ecommerce_status = request.POST.get("ecommerceStatus", "")
        if ecommerce_status in ("OPEN", "CONFIRM"):
            logger.debug(
                "[django_athm:intermediate_status]",
                extra={"status": ecommerce_status},
            )
            return HttpResponse(status=200)

        # Extract ecommerceId - the only field we trust from POST
        ecommerce_id = request.POST.get("ecommerceId", "")
        if not ecommerce_id:
            logger.error("[django_athm:missing_ecommerce_id]")
            return JsonResponse({"error": "Missing ecommerceId"}, status=400)

        # Server-side verification - fetch transaction data from API
        try:
            client = ATHMovilClient(
                public_token=django_settings.DJANGO_ATHM_PUBLIC_TOKEN,
                private_token=django_settings.DJANGO_ATHM_PRIVATE_TOKEN,
            )
            verification = client.find_payment(ecommerce_id=ecommerce_id)
            data = verification.data
        except ATHMovilError as e:
            logger.error(
                "[django_athm:verification_failed]",
                extra={"ecommerce_id": ecommerce_id, "error": str(e)},
            )
            return JsonResponse(
                {"error": "Transaction verification failed"}, status=400
            )

        # Extract verified data from API response
        reference_number = data.reference_number
        if not reference_number:
            logger.error(
                "[django_athm:missing_reference_number]",
                extra={"ecommerce_id": ecommerce_id},
            )
            return JsonResponse({"error": "Transaction not yet completed"}, status=400)

        total = data.total or Decimal("0")
        subtotal = data.sub_total
        tax = data.tax
        fee = data.fee
        net_amount = data.net_amount
        metadata_1 = data.metadata1
        metadata_2 = data.metadata2

        # Get ecommerce_status from verified response
        ecommerce_status = data.ecommerce_status.value if data.ecommerce_status else ""

        # Map ecommerce status to internal status
        status_mapping = {
            "COMPLETED": models.ATHM_Transaction.Status.COMPLETED,
            "CANCEL": models.ATHM_Transaction.Status.CANCEL,
            "CANCELLED": models.ATHM_Transaction.Status.CANCEL,
            "EXPIRED": models.ATHM_Transaction.Status.CANCEL,
            "OPEN": models.ATHM_Transaction.Status.OPEN,
            "CONFIRM": models.ATHM_Transaction.Status.CONFIRM,
            "REFUNDED": models.ATHM_Transaction.Status.REFUNDED,
        }
        internal_status = status_mapping.get(
            ecommerce_status, models.ATHM_Transaction.Status.COMPLETED
        )

        # Use transaction date from API response, fallback to now
        transaction_date = data.transaction_date
        if transaction_date:
            if not is_aware(transaction_date):
                transaction_date = make_aware(transaction_date)
        else:
            transaction_date = timezone.now()

        # Create or update transaction (idempotent for duplicate callbacks)
        transaction_obj, created = models.ATHM_Transaction.objects.update_or_create(
            reference_number=reference_number,
            defaults={
                "status": internal_status,
                "total": total,
                "subtotal": subtotal,
                "tax": tax,
                "fee": fee,
                "metadata_1": metadata_1,
                "metadata_2": metadata_2,
                "ecommerce_id": ecommerce_id,
                "ecommerce_status": ecommerce_status,
                "net_amount": net_amount,
                "date": transaction_date,
            },
        )

        logger.info(
            "[django_athm:transaction_created]"
            if created
            else "[django_athm:transaction_updated]",
            extra={
                "transaction_id": str(transaction_obj.id),
                "reference_number": reference_number,
                "total": str(total),
                "status": internal_status,
                "created": created,
            },
        )

        # Process items from verified API response
        if not created:
            transaction_obj.items.all().delete()

        if data.items:
            item_instances = []
            for item in data.items:
                item_instances.append(
                    models.ATHM_Item(
                        transaction=transaction_obj,
                        name=(item.name or "")[:32],
                        description=(item.description or "")[:128],
                        quantity=int(item.quantity or 1),
                        price=item.price or Decimal("0"),
                        tax=item.tax,
                        metadata=item.metadata,
                    )
                )

            if item_instances:
                models.ATHM_Item.objects.bulk_create(item_instances)
                logger.debug(
                    "[django_athm:items_created]",
                    extra={
                        "transaction_id": str(transaction_obj.id),
                        "item_count": len(item_instances),
                    },
                )

        # Dispatch signals after all data is persisted
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
            if ecommerce_status == "EXPIRED":
                athm_expired_response.send(
                    sender=models.ATHM_Transaction,
                    transaction=transaction_obj,
                )
            else:
                athm_cancelled_response.send(
                    sender=models.ATHM_Transaction,
                    transaction=transaction_obj,
                )

        return HttpResponse(status=201 if created else 200)

    except Exception as e:
        logger.exception(
            "[django_athm:callback_error]",
            extra={"error": str(e)},
        )
        return JsonResponse(
            {"error": "Internal server error processing payment callback"},
            status=500,
        )
