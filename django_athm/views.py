import json
import logging
from uuid import UUID

from athm import parse_webhook
from athm.exceptions import ValidationError as ATHMValidationError
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django_athm.models import Payment
from django_athm.services import PaymentService, WebhookProcessor
from django_athm.utils import safe_decimal, validate_phone_number, validate_total

logger = logging.getLogger(__name__)

# Session key template for storing auth tokens
SESSION_AUTH_TOKEN_KEY = "athm_auth_{}"


def _parse_json_body(request: HttpRequest) -> tuple[dict | None, JsonResponse | None]:
    """
    Parse JSON body from request.

    Returns:
        (data, None) on success
        (None, error_response) on failure
    """
    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON"}, status=400)


def _get_client_ip(request) -> str:
    """Extract client IP from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _parse_ecommerce_id(
    ecommerce_id: str | None,
) -> tuple[UUID | None, JsonResponse | None]:
    """
    Validate and parse ecommerce_id.

    Returns:
        (uuid, None) on success
        (None, error_response) on failure
    """
    if not ecommerce_id:
        return None, JsonResponse({"error": "Missing ecommerce_id"}, status=400)

    try:
        return UUID(str(ecommerce_id)), None
    except ValueError:
        return None, JsonResponse({"error": "Invalid ecommerce_id"}, status=400)


def _get_payment(ecommerce_uuid: UUID) -> tuple[Payment | None, JsonResponse | None]:
    """
    Fetch payment by UUID.

    Returns:
        (payment, None) on success
        (None, error_response) on failure
    """
    try:
        return Payment.objects.get(ecommerce_id=ecommerce_uuid), None
    except Payment.DoesNotExist:
        return None, JsonResponse({"error": "Payment not found"}, status=404)


def process_webhook_request(request):
    """Process ATH Móvil webhook request with idempotency."""
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning("[django-athm] Malformed webhook payload")
        return HttpResponse(status=200)

    # Store event (computes idempotency from raw payload)
    event, created = WebhookProcessor.store_event(
        payload=payload,
        remote_ip=_get_client_ip(request),
    )

    if not created:
        logger.debug("[django-athm] Duplicate webhook: %s", event.idempotency_key)
        return HttpResponse(status=200)

    # Parse and validate payload
    try:
        normalized = parse_webhook(payload)
    except ATHMValidationError as e:
        logger.error(
            "[django-athm] Invalid webhook payload for event %s: %s",
            event.id,
            str(e),
        )
        # Mark as processed to prevent retry
        WebhookProcessor.mark_processed(event)
        return HttpResponse(status=200)

    # Process the validated event
    try:
        WebhookProcessor.process(event, normalized)
    except Exception:
        logger.exception("[django-athm] Webhook processing failed: %s", event.id)

    return HttpResponse(status=200)


@csrf_exempt
@require_http_methods(["POST"])
def webhook(request):
    return process_webhook_request(request)


@require_http_methods(["POST"])
def initiate(request):
    data, error = _parse_json_body(request)
    if error:
        return error

    # Validate required fields
    try:
        total = validate_total(data.get("total"))
        phone_number = validate_phone_number(data.get("phone_number"))
    except ValidationError as e:
        return JsonResponse({"error": str(e.message)}, status=400)

    # Optional fields (None if not provided)
    raw_subtotal = data.get("subtotal")
    raw_tax = data.get("tax")
    subtotal = safe_decimal(raw_subtotal) if raw_subtotal is not None else None
    tax = safe_decimal(raw_tax) if raw_tax is not None else None

    try:
        payment, auth_token = PaymentService.initiate(
            total=total,
            subtotal=subtotal,
            tax=tax,
            metadata_1=str(data.get("metadata_1", ""))[:40],
            metadata_2=str(data.get("metadata_2", ""))[:40],
            items=data.get("items"),
            phone_number=phone_number,
        )
    except Exception as e:
        logger.exception("[django-athm] Failed to initiate payment")
        return JsonResponse({"error": str(e)}, status=500)

    # Store auth_token in session for later authorization
    request.session[SESSION_AUTH_TOKEN_KEY.format(payment.ecommerce_id)] = auth_token

    return JsonResponse(
        {
            "ecommerce_id": str(payment.ecommerce_id),
            "status": payment.status,
        }
    )


@require_http_methods(["GET"])
def status(request):
    ecommerce_uuid, error = _parse_ecommerce_id(request.GET.get("ecommerce_id"))
    if error:
        return error

    payment, error = _get_payment(ecommerce_uuid)
    if error:
        return error

    PaymentService.sync_status(payment)

    return JsonResponse(
        {
            "status": payment.status,
            "reference_number": payment.reference_number,
        }
    )


@require_http_methods(["POST"])
def authorize(request):
    data, error = _parse_json_body(request)
    if error:
        return error

    ecommerce_uuid, error = _parse_ecommerce_id(data.get("ecommerce_id"))
    if error:
        return error

    # Get auth token from session
    auth_token = request.session.get(SESSION_AUTH_TOKEN_KEY.format(ecommerce_uuid))
    if not auth_token:
        logger.warning(
            "[django-athm] No auth token in session for payment %s", ecommerce_uuid
        )
        return JsonResponse({"error": "Session expired"}, status=400)

    payment, error = _get_payment(ecommerce_uuid)
    if error:
        return error

    # Check current status
    if payment.status == Payment.Status.COMPLETED:
        return JsonResponse(
            {
                "status": payment.status,
                "reference_number": payment.reference_number,
            }
        )

    if payment.status == Payment.Status.CANCEL:
        return JsonResponse({"error": "Payment was cancelled"}, status=400)

    if payment.status not in (Payment.Status.OPEN, Payment.Status.CONFIRM):
        return JsonResponse({"error": f"Invalid status: {payment.status}"}, status=400)

    try:
        reference_number = PaymentService.authorize(ecommerce_uuid, auth_token)
    except Exception as e:
        logger.exception("[django-athm] Failed to authorize payment %s", ecommerce_uuid)
        return JsonResponse({"error": str(e)}, status=500)

    # Update local status optimistically
    # Webhook will confirm with full details (fee, net_amount, etc.)
    payment.status = Payment.Status.COMPLETED
    payment.reference_number = reference_number
    payment.save(update_fields=["status", "reference_number", "updated_at"])

    # Clean up session
    request.session.pop(SESSION_AUTH_TOKEN_KEY.format(ecommerce_uuid), None)

    return JsonResponse(
        {
            "status": payment.status,
            "reference_number": payment.reference_number,
        }
    )


@require_http_methods(["POST"])
def cancel(request):
    data, error = _parse_json_body(request)
    if error:
        return error

    ecommerce_uuid, error = _parse_ecommerce_id(data.get("ecommerce_id"))
    if error:
        return error

    try:
        PaymentService.cancel(ecommerce_uuid)
    except Exception as e:
        logger.warning(
            "[django-athm] Failed to cancel payment %s: %s", ecommerce_uuid, e
        )
        # Still return success - payment may have already completed

    # Clean up session
    request.session.pop(SESSION_AUTH_TOKEN_KEY.format(ecommerce_uuid), None)

    return JsonResponse({"status": "cancelled"})
