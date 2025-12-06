"""
Webhook processing for ATH Móvil events.

Handles incoming webhook requests, validates payloads, and processes
transactions following patterns from dj-stripe.
"""
import json
import logging
from decimal import Decimal
from traceback import format_exc
from typing import Any, Optional

from athm.exceptions import ValidationError as ATHMValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import models, signals
from .client import ATHMClient

logger = logging.getLogger(__name__)


def get_remote_ip(request: HttpRequest) -> str:
    """
    Get the client IP address from the request.

    Args:
        request: Django HTTP request

    Returns:
        IP address string
    """
    # Check for forwarded IP (when behind proxy/load balancer)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _safe_decimal(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """
    Safely convert a value to Decimal.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Decimal or default
    """
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return default


def _map_transaction_status(athm_status: str) -> str:
    """
    Map ATH Móvil API status to django-athm model status.

    Args:
        athm_status: Status from ATH Móvil

    Returns:
        Status value for ATHM_Transaction.Status
    """
    status_map = {
        "COMPLETED": models.ATHM_Transaction.Status.COMPLETED,
        "CANCELLED": models.ATHM_Transaction.Status.CANCELLED,
        "CANCEL": models.ATHM_Transaction.Status.CANCEL,
        "EXPIRED": models.ATHM_Transaction.Status.EXPIRED,
        "OPEN": models.ATHM_Transaction.Status.OPEN,
        "CONFIRM": models.ATHM_Transaction.Status.CONFIRM,
        "REFUNDED": models.ATHM_Transaction.Status.REFUNDED,
    }
    return status_map.get(athm_status.upper(), models.ATHM_Transaction.Status.OPEN)


def _determine_event_type(webhook_data: dict[str, Any]) -> str:
    """
    Determine the event type from webhook data.

    Args:
        webhook_data: Parsed webhook payload

    Returns:
        EventType value
    """
    transaction_type = webhook_data.get("transaction_type", "").upper()
    status = webhook_data.get("status", "").upper()

    # Map to our EventType choices
    if transaction_type == "ECOMMERCE":
        if status == "COMPLETED":
            return models.ATHM_WebhookEvent.EventType.ECOMMERCE_COMPLETED
        elif status in ("CANCELLED", "CANCEL"):
            return models.ATHM_WebhookEvent.EventType.ECOMMERCE_CANCELLED
        elif status == "EXPIRED":
            return models.ATHM_WebhookEvent.EventType.ECOMMERCE_EXPIRED
    elif transaction_type == "REFUND":
        return models.ATHM_WebhookEvent.EventType.REFUND_SENT
    elif transaction_type == "PAYMENT":
        return models.ATHM_WebhookEvent.EventType.PAYMENT_RECEIVED

    return models.ATHM_WebhookEvent.EventType.UNKNOWN


def process_webhook_data(
    webhook_event: models.ATHM_WebhookEvent, webhook_data: dict[str, Any]
) -> Optional[models.ATHM_Transaction]:
    """
    Process validated webhook data and create/update transaction.

    Args:
        webhook_event: The webhook event record
        webhook_data: Parsed and validated webhook payload

    Returns:
        Created or updated ATHM_Transaction, or None if processing failed
    """
    try:
        # Extract data from webhook
        reference_number = webhook_data.get("reference_number")
        ecommerce_id = webhook_data.get("ecommerce_id")
        status = webhook_data.get("status", "")

        # Map status
        transaction_status = _map_transaction_status(status)

        # Find or create transaction
        transaction_obj = None

        # Try to find by reference_number first (most reliable)
        if reference_number:
            transaction_obj = models.ATHM_Transaction.objects.filter(
                reference_number=reference_number
            ).first()

        # Fall back to ecommerce_id if no reference_number
        if not transaction_obj and ecommerce_id:
            transaction_obj = models.ATHM_Transaction.objects.filter(
                ecommerce_id=ecommerce_id
            ).first()

        # Create new transaction if not found
        if not transaction_obj:
            if not reference_number:
                # We need at least a reference number to create a transaction
                logger.warning(
                    "[django_athm:webhook:no_reference_number]",
                    extra={"webhook_event_id": webhook_event.id},
                )
                return None

            transaction_obj = models.ATHM_Transaction(
                reference_number=reference_number,
                status=transaction_status,
            )
            logger.info(
                "[django_athm:webhook:creating_transaction]",
                extra={"reference_number": reference_number},
            )
        else:
            # Update existing transaction
            transaction_obj.status = transaction_status
            logger.info(
                "[django_athm:webhook:updating_transaction]",
                extra={
                    "transaction_id": str(transaction_obj.id),
                    "new_status": transaction_status,
                },
            )

        # Update fields from webhook data
        if ecommerce_id:
            transaction_obj.ecommerce_id = ecommerce_id

        if daily_transaction_id := webhook_data.get("daily_transaction_id"):
            transaction_obj.daily_transaction_id = daily_transaction_id

        # Update monetary fields
        if total := webhook_data.get("total"):
            transaction_obj.total = _safe_decimal(total, Decimal("0"))

        if subtotal := webhook_data.get("subtotal"):
            transaction_obj.subtotal = _safe_decimal(subtotal)

        if tax := webhook_data.get("tax"):
            transaction_obj.tax = _safe_decimal(tax)

        if fee := webhook_data.get("fee"):
            transaction_obj.fee = _safe_decimal(fee)

        # Update customer info
        if customer_name := webhook_data.get("customer_name"):
            transaction_obj.customer_name = customer_name

        if customer_phone := webhook_data.get("customer_phone"):
            transaction_obj.customer_phone = customer_phone

        # Update business info
        if business_name := webhook_data.get("business_name"):
            transaction_obj.business_name = business_name

        # Update metadata
        if metadata1 := webhook_data.get("metadata1"):
            transaction_obj.metadata_1 = metadata1

        if metadata2 := webhook_data.get("metadata2"):
            transaction_obj.metadata_2 = metadata2

        # Update date if present
        if date_str := webhook_data.get("date"):
            # ATH Móvil webhook should include date
            # We'll store it as-is; python-athm should handle parsing
            transaction_obj.date = timezone.now()

        # Save transaction
        transaction_obj.save()

        # Process items if present
        if items := webhook_data.get("items"):
            _process_transaction_items(transaction_obj, items)

        logger.info(
            "[django_athm:webhook:transaction_processed]",
            extra={
                "transaction_id": str(transaction_obj.id),
                "reference_number": transaction_obj.reference_number,
                "status": transaction_obj.status,
            },
        )

        return transaction_obj

    except Exception as e:
        logger.exception(
            "[django_athm:webhook:processing_error]",
            extra={"webhook_event_id": webhook_event.id, "error": str(e)},
        )
        raise


def _process_transaction_items(
    transaction_obj: models.ATHM_Transaction, items: list[dict[str, Any]]
) -> None:
    """
    Process and create transaction items.

    Args:
        transaction_obj: The transaction to attach items to
        items: List of item dictionaries from webhook
    """
    # Clear existing items (webhook is source of truth)
    transaction_obj.items.all().delete()

    item_instances = []
    for item_data in items:
        item_instances.append(
            models.ATHM_Item(
                transaction=transaction_obj,
                name=item_data.get("name", "")[:128],
                description=item_data.get("description", "")[:255],
                quantity=item_data.get("quantity", 1),
                price=_safe_decimal(item_data.get("price"), Decimal("0")),
                tax=_safe_decimal(item_data.get("tax")),
                metadata=item_data.get("metadata", "")[:64] if item_data.get("metadata") else None,
            )
        )

    if item_instances:
        models.ATHM_Item.objects.bulk_create(item_instances)
        logger.debug(
            "[django_athm:webhook:items_created]",
            extra={
                "transaction_id": str(transaction_obj.id),
                "item_count": len(item_instances),
            },
        )


@csrf_exempt
@require_POST
def webhook_view(request: HttpRequest) -> HttpResponse:
    """
    Handle incoming ATH Móvil webhook requests.

    This view:
    1. Logs the raw webhook request
    2. Validates the webhook payload using python-athm
    3. Creates/updates transaction records
    4. Sends Django signals
    5. Returns appropriate HTTP responses

    Similar to dj-stripe's webhook handling pattern.
    """
    # Get request metadata
    remote_ip = get_remote_ip(request)
    headers = dict(request.headers)
    body = request.body.decode("utf-8")

    logger.info(
        "[django_athm:webhook:received]",
        extra={"remote_ip": remote_ip, "content_length": len(body)},
    )

    # Create webhook event record
    webhook_event = models.ATHM_WebhookEvent.objects.create(
        remote_ip=remote_ip,
        headers=headers,
        body=body,
        valid=False,
        processed=False,
    )

    try:
        # Parse JSON payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(
                "[django_athm:webhook:invalid_json]",
                extra={"webhook_event_id": webhook_event.id, "error": str(e)},
            )
            webhook_event.exception = "Invalid JSON"
            webhook_event.traceback = format_exc()
            webhook_event.save(update_fields=["exception", "traceback"])
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # Validate webhook using python-athm
        client = ATHMClient()
        try:
            webhook_data = client.parse_webhook(payload)
            webhook_event.valid = True
            webhook_event.event_type = _determine_event_type(webhook_data)
            webhook_event.transaction_status = webhook_data.get("status", "")
            webhook_event.save(
                update_fields=["valid", "event_type", "transaction_status"]
            )

            logger.debug(
                "[django_athm:webhook:validated]",
                extra={
                    "webhook_event_id": webhook_event.id,
                    "event_type": webhook_event.event_type,
                },
            )

        except ATHMValidationError as e:
            logger.error(
                "[django_athm:webhook:validation_failed]",
                extra={"webhook_event_id": webhook_event.id, "error": str(e)},
            )
            webhook_event.exception = f"Validation failed: {e}"
            webhook_event.traceback = format_exc()
            webhook_event.save(update_fields=["exception", "traceback"])
            return JsonResponse({"error": "Invalid webhook payload"}, status=400)

        # Process the webhook in a transaction
        with transaction.atomic():
            transaction_obj = process_webhook_data(webhook_event, webhook_data)

            if transaction_obj:
                webhook_event.transaction = transaction_obj
                webhook_event.processed = True
                webhook_event.save(update_fields=["transaction", "processed"])

                # Send Django signals
                _send_webhook_signals(webhook_event, transaction_obj, webhook_data)

                logger.info(
                    "[django_athm:webhook:success]",
                    extra={
                        "webhook_event_id": webhook_event.id,
                        "transaction_id": str(transaction_obj.id),
                    },
                )

                return JsonResponse({"status": "success"}, status=200)
            else:
                webhook_event.exception = "Failed to process transaction"
                webhook_event.save(update_fields=["exception"])
                return JsonResponse({"error": "Processing failed"}, status=500)

    except Exception as e:
        logger.exception(
            "[django_athm:webhook:error]",
            extra={"webhook_event_id": webhook_event.id, "error": str(e)},
        )
        webhook_event.exception = str(e)[:255]
        webhook_event.traceback = format_exc()
        webhook_event.save(update_fields=["exception", "traceback"])
        return JsonResponse({"error": "Internal server error"}, status=500)


def _send_webhook_signals(
    webhook_event: models.ATHM_WebhookEvent,
    transaction_obj: models.ATHM_Transaction,
    webhook_data: dict[str, Any],
) -> None:
    """
    Send Django signals for webhook events.

    Args:
        webhook_event: The webhook event record
        transaction_obj: The associated transaction
        webhook_data: Parsed webhook payload
    """
    # Send general signal
    signals.athm_response_received.send(
        sender=models.ATHM_Transaction,
        transaction=transaction_obj,
        webhook_event=webhook_event,
        data=webhook_data,
    )

    # Send status-specific signals
    status = transaction_obj.status.lower()

    if status == models.ATHM_Transaction.Status.COMPLETED:
        signals.athm_completed_response.send(
            sender=models.ATHM_Transaction,
            transaction=transaction_obj,
            webhook_event=webhook_event,
            data=webhook_data,
        )
    elif status in (
        models.ATHM_Transaction.Status.CANCEL,
        models.ATHM_Transaction.Status.CANCELLED,
    ):
        signals.athm_cancelled_response.send(
            sender=models.ATHM_Transaction,
            transaction=transaction_obj,
            webhook_event=webhook_event,
            data=webhook_data,
        )
    elif status == models.ATHM_Transaction.Status.EXPIRED:
        signals.athm_expired_response.send(
            sender=models.ATHM_Transaction,
            transaction=transaction_obj,
            webhook_event=webhook_event,
            data=webhook_data,
        )

    logger.debug(
        "[django_athm:webhook:signals_sent]",
        extra={
            "transaction_id": str(transaction_obj.id),
            "status": status,
        },
    )
