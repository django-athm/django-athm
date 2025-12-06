"""
Payment views for ATH Móvil Payment Button API.

Handles payment creation and status polling for the backend-first payment flow.
"""
import logging
from decimal import Decimal
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import models
from .client import ATHMClient
from .utils import safe_decimal

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def create_payment_view(request: HttpRequest) -> JsonResponse:
    """
    Create a new ATH Móvil payment using the Payment Button API.

    Expected POST data:
    - phone_number: Customer's phone number (required)
    - total: Total amount (required)
    - subtotal: Subtotal amount (optional)
    - tax: Tax amount (optional)
    - metadata1: Custom metadata field 1 (optional)
    - metadata2: Custom metadata field 2 (optional)
    - items: JSON array of line items (optional)

    Returns:
    - 200: Payment created successfully with ecommerce_id
    - 400: Invalid request data
    - 500: Payment creation failed
    """
    try:
        # Extract payment data from request
        phone_number = request.POST.get("phone_number", "").strip()
        total = request.POST.get("total", "")
        subtotal = request.POST.get("subtotal")
        tax = request.POST.get("tax")
        metadata1 = request.POST.get("metadata1")
        metadata2 = request.POST.get("metadata2")

        # Validate required fields
        if not phone_number:
            return JsonResponse(
                {"error": _("Phone number is required")}, status=400
            )

        if not total:
            return JsonResponse({"error": _("Total amount is required")}, status=400)

        # Convert monetary values
        total_decimal = safe_decimal(total)
        if total_decimal is None or total_decimal <= 0:
            return JsonResponse({"error": _("Invalid total amount")}, status=400)

        # Create payment via ATH Móvil API
        client = ATHMClient()

        # TODO: Handle items from request.POST (JSON array)
        items = None

        logger.info(
            "[django_athm:payment:creating]",
            extra={
                "phone_number": phone_number,
                "total": str(total_decimal),
            },
        )

        # Call Payment Button API
        response = client.create_payment(
            total=float(total_decimal),
            phone_number=phone_number,
            metadata1=metadata1,
            metadata2=metadata2,
            items=items,
        )

        # Extract ecommerce_id from response
        ecommerce_id = response.get("ecommerce_id")
        if not ecommerce_id:
            logger.error(
                "[django_athm:payment:no_ecommerce_id]",
                extra={"response": response},
            )
            return JsonResponse(
                {"error": _("Failed to create payment - no ecommerce_id")},
                status=500,
            )

        # Create transaction record in OPEN status
        transaction = models.ATHM_Transaction.objects.create(
            ecommerce_id=ecommerce_id,
            status=models.ATHM_Transaction.Status.OPEN,
            total=total_decimal,
            subtotal=safe_decimal(subtotal),
            tax=safe_decimal(tax),
            customer_phone=phone_number,
            metadata_1=metadata1 or "",
            metadata_2=metadata2 or "",
        )

        logger.info(
            "[django_athm:payment:created]",
            extra={
                "ecommerce_id": ecommerce_id,
                "transaction_id": str(transaction.id),
            },
        )

        return JsonResponse(
            {
                "status": "success",
                "ecommerce_id": ecommerce_id,
                "transaction_id": str(transaction.id),
            },
            status=200,
        )

    except Exception as e:
        logger.exception(
            "[django_athm:payment:error]",
            extra={"error": str(e)},
        )
        return JsonResponse(
            {"error": _("An error occurred while creating the payment")},
            status=500,
        )


@require_GET
def payment_status_view(request: HttpRequest, ecommerce_id: str) -> JsonResponse:
    """
    Poll payment status for a given ecommerce_id.

    Used by frontend to poll for payment confirmation while user
    is authorizing on their phone.

    Returns:
    - 200: Status information
      - status: Transaction status (OPEN, CONFIRM, COMPLETED, CANCELLED, EXPIRED)
      - needs_auth: Boolean indicating if backend needs to authorize
      - message: User-friendly status message
    - 404: Transaction not found
    """
    try:
        # Find transaction by ecommerce_id
        transaction = models.ATHM_Transaction.objects.filter(
            ecommerce_id=ecommerce_id
        ).first()

        if not transaction:
            return JsonResponse({"error": _("Payment not found")}, status=404)

        # Determine status and message
        status = transaction.status
        needs_auth = False
        message = ""

        if status == models.ATHM_Transaction.Status.OPEN:
            message = _("Waiting for confirmation...")
        elif status == models.ATHM_Transaction.Status.CONFIRM:
            message = _("Confirming payment...")
            needs_auth = True
        elif status == models.ATHM_Transaction.Status.COMPLETED:
            message = _("Payment completed successfully!")
        elif status == models.ATHM_Transaction.Status.CANCELLED:
            message = _("Payment was cancelled")
        elif status == models.ATHM_Transaction.Status.EXPIRED:
            message = _("Payment expired")
        else:
            message = _("Unknown status")

        logger.debug(
            "[django_athm:payment:status_check]",
            extra={
                "ecommerce_id": ecommerce_id,
                "status": status,
                "needs_auth": needs_auth,
            },
        )

        return JsonResponse(
            {
                "status": status,
                "needs_auth": needs_auth,
                "message": message,
                "reference_number": transaction.reference_number or "",
            },
            status=200,
        )

    except Exception as e:
        logger.exception(
            "[django_athm:payment:status_error]",
            extra={"ecommerce_id": ecommerce_id, "error": str(e)},
        )
        return JsonResponse(
            {"error": _("An error occurred while checking payment status")},
            status=500,
        )
