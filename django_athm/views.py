import json
import logging
from uuid import UUID

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django_athm.models import Payment
from django_athm.services import PaymentService, WebhookProcessor
from django_athm.utils import safe_decimal, validate_phone_number, validate_total

logger = logging.getLogger(__name__)


def _get_client_ip(request) -> str:
    """Extract client IP from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


@csrf_exempt
@require_http_methods(["POST"])
def webhook(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning("[django-athm] Received malformed webhook payload")
        return HttpResponse(status=200)

    event, created = WebhookProcessor.store_event(
        payload=payload,
        remote_ip=_get_client_ip(request),
    )

    if not created:
        logger.debug(
            f"[django-athm] Duplicate webhook received: {event.idempotency_key}"
        )
        return HttpResponse(status=200)

    # Process the event
    try:
        WebhookProcessor.process(event)
    except Exception:
        logger.exception(f"[django-athm] Webhook processing failed: {event.id}")

    return HttpResponse(status=200)


@require_http_methods(["POST"])
def initiate(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Validate required fields
    try:
        total = validate_total(data.get("total"))
        phone_number = validate_phone_number(data.get("phone_number"))
    except ValidationError as e:
        return JsonResponse({"error": str(e.message)}, status=400)

    # Optional fields
    subtotal = safe_decimal(data.get("subtotal"))
    tax = safe_decimal(data.get("tax"))

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
    request.session[f"athm_auth_{payment.ecommerce_id}"] = auth_token

    logger.info(f"[django-athm] Payment {payment.ecommerce_id} initiated via API")

    return JsonResponse(
        {
            "ecommerce_id": str(payment.ecommerce_id),
            "status": payment.status,
        }
    )


@require_http_methods(["GET"])
def status(request):
    ecommerce_id = request.GET.get("ecommerce_id")
    if not ecommerce_id:
        return JsonResponse({"error": "Missing ecommerce_id"}, status=400)

    try:
        ecommerce_uuid = UUID(str(ecommerce_id))
    except ValueError:
        return JsonResponse({"error": "Invalid ecommerce_id"}, status=400)

    try:
        payment = Payment.objects.get(ecommerce_id=ecommerce_uuid)
    except Payment.DoesNotExist:
        return JsonResponse({"error": "Payment not found"}, status=404)

    # Sync with remote status if needed
    PaymentService.sync_status(payment)

    return JsonResponse(
        {
            "status": payment.status,
            "reference_number": payment.reference_number,
        }
    )


@require_http_methods(["POST"])
def authorize(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    ecommerce_id = data.get("ecommerce_id")
    if not ecommerce_id:
        return JsonResponse({"error": "Missing ecommerce_id"}, status=400)

    try:
        ecommerce_uuid = UUID(str(ecommerce_id))
    except ValueError:
        return JsonResponse({"error": "Invalid ecommerce_id"}, status=400)

    # Get auth token from session
    auth_token = request.session.get(f"athm_auth_{ecommerce_id}")
    if not auth_token:
        logger.warning(
            f"[django-athm] No auth token in session for payment {ecommerce_id}"
        )
        return JsonResponse({"error": "Session expired"}, status=400)

    try:
        payment = Payment.objects.get(ecommerce_id=ecommerce_uuid)
    except Payment.DoesNotExist:
        return JsonResponse({"error": "Payment not found"}, status=404)

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
        logger.exception(f"[django-athm] Failed to authorize payment {ecommerce_id}")
        return JsonResponse({"error": str(e)}, status=500)

    # Update local status optimistically
    # Webhook will confirm with full details (fee, net_amount, etc.)
    payment.status = Payment.Status.COMPLETED
    payment.reference_number = reference_number
    payment.save(update_fields=["status", "reference_number", "modified"])

    logger.info(
        f"[django-athm] Authorized payment {ecommerce_id} -> {reference_number}"
    )

    # Clean up session
    request.session.pop(f"athm_auth_{ecommerce_id}", None)

    return JsonResponse(
        {
            "status": payment.status,
            "reference_number": payment.reference_number,
        }
    )


@require_http_methods(["POST"])
def cancel(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    ecommerce_id = data.get("ecommerce_id")
    if not ecommerce_id:
        return JsonResponse({"error": "Missing ecommerce_id"}, status=400)

    try:
        ecommerce_uuid = UUID(str(ecommerce_id))
    except ValueError:
        return JsonResponse({"error": "Invalid ecommerce_id"}, status=400)

    try:
        PaymentService.cancel(ecommerce_uuid)
        logger.info(f"[django-athm] Payment {ecommerce_id} cancelled via API")
    except Exception as e:
        logger.warning(f"[django-athm] Failed to cancel payment {ecommerce_id}: {e}")
        # Still return success - payment may have already completed

    # Clean up session
    request.session.pop(f"athm_auth_{ecommerce_id}", None)

    return JsonResponse({"status": "cancelled"})
