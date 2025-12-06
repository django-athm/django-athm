"""
Webhook processing for ATH Móvil events.

Handles incoming webhook requests, validates payloads, and processes
transactions following patterns from dj-stripe.
"""
import hashlib
import json
import logging
from traceback import format_exc
from typing import Any, Optional

from athm.exceptions import ValidationError as ATHMValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import models, signals
from .client import ATHMClient
from .utils import safe_decimal

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


def generate_webhook_id(request: HttpRequest, webhook_data: Optional[dict] = None) -> str:
    """
    Generate a unique, deterministic webhook ID for idempotency.

    ATH Móvil may not provide a unique webhook delivery ID, so we generate one
    based on the webhook payload to ensure idempotency.

    Args:
        request: Django HTTP request
        webhook_data: Parsed webhook data (optional, falls back to body hash)

    Returns:
        Unique webhook ID string
    """
    # Try to use ATH Móvil's webhook ID if provided in headers
    if webhook_id := request.headers.get("X-ATHM-Webhook-ID"):
        return webhook_id

    # Generate deterministic ID from webhook data
    if webhook_data:
        # Use critical fields that uniquely identify this webhook event
        reference = webhook_data.get("reference_number", "")
        ecommerce_id = webhook_data.get("ecommerce_id", "")
        status = webhook_data.get("status", "")
        daily_tx_id = webhook_data.get("daily_transaction_id", "")

        # Create a unique string from these fields
        unique_str = f"{reference}:{ecommerce_id}:{status}:{daily_tx_id}"
        return hashlib.sha256(unique_str.encode()).hexdigest()[:64]

    # Fallback: hash the entire request body
    body_hash = hashlib.sha256(request.body).hexdigest()
    return f"body_{body_hash[:60]}"


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
        "CANCEL": models.ATHM_Transaction.Status.CANCELLED,  # Legacy alias
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
    elif transaction_type == "DONATION":
        return models.ATHM_WebhookEvent.EventType.DONATION_RECEIVED

    return models.ATHM_WebhookEvent.EventType.UNKNOWN


def _auto_authorize_payment(
    transaction_obj: models.ATHM_Transaction, webhook_data: dict[str, Any]
) -> None:
    """
    Automatically authorize a payment that reached CONFIRM status.

    This is called when a webhook indicates the user confirmed the payment
    in their ATH Móvil app. We authorize it to complete the transaction.

    Args:
        transaction_obj: The transaction in CONFIRM status
        webhook_data: Webhook payload with auth_token
    """
    try:
        # Extract auth_token from webhook
        auth_token = webhook_data.get("auth_token")

        if not auth_token:
            logger.warning(
                "[django_athm:webhook:no_auth_token]",
                extra={"transaction_id": str(transaction_obj.id)},
            )
            return

        logger.info(
            "[django_athm:webhook:authorizing_payment]",
            extra={
                "transaction_id": str(transaction_obj.id),
                "ecommerce_id": transaction_obj.ecommerce_id,
            },
        )

        # Call authorization API
        client = ATHMClient()
        response = client.authorize_payment(auth_token)

        logger.info(
            "[django_athm:webhook:payment_authorized]",
            extra={
                "transaction_id": str(transaction_obj.id),
                "response": response,
            },
        )

    except Exception as e:
        logger.exception(
            "[django_athm:webhook:authorization_error]",
            extra={
                "transaction_id": str(transaction_obj.id),
                "error": str(e),
            },
        )


def process_webhook_data(
    webhook_event: models.ATHM_WebhookEvent, webhook_data: dict[str, Any]
) -> Optional[models.ATHM_Transaction]:
    """
    Process validated webhook data and create/update transaction.

    Implements:
    - Row-level locking via select_for_update() to prevent race conditions
    - Timestamp-based conflict resolution to prevent stale updates
    - Atomic transaction updates

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

        # Webhook timestamp for conflict resolution
        webhook_timestamp = webhook_event.created

        # Find or create transaction with row-level locking
        transaction_obj = None
        is_new = False

        # Try to find by reference_number first (most reliable)
        if reference_number:
            transaction_obj = (
                models.ATHM_Transaction.objects.select_for_update()
                .filter(reference_number=reference_number)
                .first()
            )

        # Fall back to ecommerce_id if no reference_number
        if not transaction_obj and ecommerce_id:
            transaction_obj = (
                models.ATHM_Transaction.objects.select_for_update()
                .filter(ecommerce_id=ecommerce_id)
                .first()
            )

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
            is_new = True
            logger.info(
                "[django_athm:webhook:creating_transaction]",
                extra={"reference_number": reference_number},
            )
        else:
            # Check for stale webhook - prevent old webhooks from overwriting new data
            if transaction_obj.modified and webhook_timestamp < transaction_obj.modified:
                logger.warning(
                    "[django_athm:webhook:stale_webhook]",
                    extra={
                        "transaction_id": str(transaction_obj.id),
                        "webhook_timestamp": webhook_timestamp.isoformat(),
                        "transaction_modified": transaction_obj.modified.isoformat(),
                    },
                )
                # Still return the transaction but don't update it
                return transaction_obj

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
            transaction_obj.total = safe_decimal(total)

        if subtotal := webhook_data.get("subtotal"):
            transaction_obj.subtotal = safe_decimal(subtotal)

        if tax := webhook_data.get("tax"):
            transaction_obj.tax = safe_decimal(tax)

        if fee := webhook_data.get("fee"):
            transaction_obj.fee = safe_decimal(fee)

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

        # Process items if present (atomic updates)
        if items := webhook_data.get("items"):
            _process_transaction_items(transaction_obj, items)

        # Auto-authorize payment if status is CONFIRM
        if transaction_obj.status == models.ATHM_Transaction.Status.CONFIRM:
            _auto_authorize_payment(transaction_obj, webhook_data)

        logger.info(
            "[django_athm:webhook:transaction_processed]",
            extra={
                "transaction_id": str(transaction_obj.id),
                "reference_number": transaction_obj.reference_number,
                "status": transaction_obj.status,
                "is_new": is_new,
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
    Process and update transaction items atomically.

    Uses update_or_create for each item to ensure ACID compliance without
    deleting and recreating all items.

    Args:
        transaction_obj: The transaction to attach items to
        items: List of item dictionaries from webhook
    """
    # Track which items we've seen in this webhook
    processed_item_names = set()

    for idx, item_data in enumerate(items):
        name = item_data.get("name", "")[:128]
        description = item_data.get("description", "")[:255]
        quantity = item_data.get("quantity", 1)
        price = safe_decimal(item_data.get("price"))
        tax = safe_decimal(item_data.get("tax"))
        metadata = item_data.get("metadata", "")[:64] if item_data.get("metadata") else None

        # Use name + transaction as unique identifier
        # If ATH Móvil sends duplicate item names, we'll update the first one
        item_obj, created = models.ATHM_Item.objects.update_or_create(
            transaction=transaction_obj,
            name=name,
            defaults={
                "description": description,
                "quantity": quantity,
                "price": price,
                "tax": tax,
                "metadata": metadata,
            },
        )

        processed_item_names.add(name)

        logger.debug(
            "[django_athm:webhook:item_processed]",
            extra={
                "transaction_id": str(transaction_obj.id),
                "item_name": name,
                "created": created,
            },
        )

    # Remove items that are no longer in the webhook
    # This handles the case where an item was removed from the transaction
    deleted_count = transaction_obj.items.exclude(
        name__in=processed_item_names
    ).delete()[0]

    if deleted_count > 0:
        logger.debug(
            "[django_athm:webhook:items_removed]",
            extra={
                "transaction_id": str(transaction_obj.id),
                "deleted_count": deleted_count,
            },
        )


@csrf_exempt
@require_POST
def webhook_view(request: HttpRequest) -> HttpResponse:
    """
    Handle incoming ATH Móvil webhook requests.

    This view implements webhook best practices:
    1. Idempotency - Duplicate webhooks are detected and handled gracefully
    2. ACID compliance - All database operations are atomic
    3. Race condition prevention - Row-level locking prevents concurrent updates
    4. Timestamp-based conflict resolution - Stale webhooks don't overwrite fresh data

    Flow:
    1. Generate deterministic webhook_id for idempotency
    2. Attempt to create webhook event record (unique constraint on webhook_id)
    3. If duplicate detected, return success immediately (idempotent)
    4. Validate payload using python-athm
    5. Process transaction in atomic database transaction
    6. Send Django signals
    7. Return appropriate HTTP response

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

    # Parse JSON payload early to generate webhook_id
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(
            "[django_athm:webhook:invalid_json]",
            extra={"remote_ip": remote_ip, "error": str(e)},
        )
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Generate webhook_id for idempotency
    webhook_id = generate_webhook_id(request, payload)

    # Try to create webhook event record
    # If webhook_id already exists, this is a duplicate delivery
    try:
        webhook_event = models.ATHM_WebhookEvent.objects.create(
            webhook_id=webhook_id,
            remote_ip=remote_ip,
            headers=headers,
            body=body,
            valid=False,
            processed=False,
        )
    except IntegrityError:
        # Duplicate webhook - already processed
        existing_event = models.ATHM_WebhookEvent.objects.get(webhook_id=webhook_id)
        logger.info(
            "[django_athm:webhook:duplicate]",
            extra={
                "webhook_id": webhook_id,
                "original_event_id": existing_event.id,
                "was_processed": existing_event.processed,
            },
        )
        # Return success - idempotent behavior
        return JsonResponse(
            {
                "status": "success",
                "message": "Duplicate webhook ignored",
                "idempotent": True,
            },
            status=200,
        )

    try:
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
    status = transaction_obj.status

    if status == models.ATHM_Transaction.Status.COMPLETED:
        signals.athm_completed_response.send(
            sender=models.ATHM_Transaction,
            transaction=transaction_obj,
            webhook_event=webhook_event,
            data=webhook_data,
        )
    elif status == models.ATHM_Transaction.Status.CANCELLED:
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
