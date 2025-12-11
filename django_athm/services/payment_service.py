import logging
from decimal import Decimal
from uuid import UUID

import httpx
from athm.client import ATHMovilClient
from athm.models import PaymentItem as ATHMovilPaymentItem
from django.db import transaction

from django_athm.conf import settings as app_settings
from django_athm.models import Payment, Refund

logger = logging.getLogger(__name__)


class PaymentService:
    """
    High-level service for managing ATH Móvil payments.

    Coordinates between local models and the ATH Móvil API via python-athm.
    """

    @classmethod
    def get_client(
        cls,
    ) -> ATHMovilClient:
        return ATHMovilClient(
            public_token=str(app_settings.PUBLIC_TOKEN),
            private_token=app_settings.PRIVATE_TOKEN,
        )

    @classmethod
    def fetch_transaction_report(
        cls,
        from_date: str,
        to_date: str,
    ) -> list[dict]:
        """
        Fetch transaction report from ATH Movil API.

        Args:
            from_date: Start date in "YYYY-MM-DD HH:MM:SS" format
            to_date: End date in "YYYY-MM-DD HH:MM:SS" format

        Returns:
            List of transaction dicts from API

        Raises:
            httpx.HTTPStatusError: On API error response
            httpx.RequestError: On network/connection failure
        """
        url = "https://www.athmovil.com/transactions/v4/transactionReport"
        payload = {
            "publicToken": str(app_settings.PUBLIC_TOKEN),
            "privateToken": app_settings.PRIVATE_TOKEN,
            "fromDate": from_date,
            "toDate": to_date,
        }

        response = httpx.get(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    @classmethod
    def initiate(
        cls,
        total: Decimal,
        phone_number: str,
        *,
        subtotal: Decimal | None = None,
        tax: Decimal | None = None,
        metadata_1: str = "",
        metadata_2: str = "",
        items: list[dict] | None = None,
    ) -> tuple[Payment, str]:
        client = cls.get_client()

        # Build items for API call
        athm_items = []
        if items:
            athm_items = [
                ATHMovilPaymentItem(
                    name=item["name"],
                    description=item.get("description", ""),
                    quantity=item.get("quantity", 1),
                    price=str(item["price"]),
                    tax=str(item.get("tax", 0)),
                    metadata=item.get("metadata", ""),
                    sku=None,
                    formattedPrice=None,
                )
                for item in items
            ]

        response = client.create_payment(
            total=str(total),
            phone_number=phone_number,
            subtotal=str(subtotal) if subtotal else None,
            tax=str(tax) if tax else None,
            metadata1=metadata_1,
            metadata2=metadata_2,
            items=athm_items,
        )

        ecommerce_id = UUID(response.data.ecommerce_id)
        auth_token = response.data.auth_token

        logger.info("[django-athm] Initiated payment %s with ATH Movil", ecommerce_id)

        # Create local record
        payment = Payment.objects.create(
            ecommerce_id=ecommerce_id,
            status=Payment.Status.OPEN,
            total=total,
            subtotal=subtotal or Decimal("0.00"),
            tax=tax or Decimal("0.00"),
            metadata_1=metadata_1,
            metadata_2=metadata_2,
        )

        logger.info("[django-athm] Created local payment record %s", ecommerce_id)

        return payment, auth_token

    @classmethod
    def update_phone_number(
        cls,
        ecommerce_id: UUID,
        phone_number: str,
        auth_token: str,
    ) -> None:
        client = cls.get_client()
        client.update_phone_number(
            ecommerce_id=str(ecommerce_id),
            phone_number=phone_number,
            auth_token=auth_token,
        )

        logger.info("[django-athm] Updated phone number for payment %s", ecommerce_id)

    @classmethod
    def find_status(cls, ecommerce_id: UUID) -> str:
        client = cls.get_client()
        transaction_response = client.find_payment(ecommerce_id=str(ecommerce_id))
        status = (
            transaction_response.data.ecommerce_status
            if transaction_response.data is not None
            else Payment.Status.OPEN
        )
        logger.debug("[django-athm] find_status %s -> %s", ecommerce_id, status)
        return status

    @classmethod
    def authorize(cls, ecommerce_id: UUID, auth_token: str) -> str:
        client = cls.get_client()
        result = client.authorize_payment(
            ecommerce_id=str(ecommerce_id), auth_token=auth_token
        )
        reference_number = (
            result.data.reference_number or "" if result.data is not None else ""
        )
        logger.info(
            "[django-athm] Authorized payment %s -> ref=%s",
            ecommerce_id,
            reference_number,
        )
        return reference_number

    @classmethod
    def cancel(cls, ecommerce_id: UUID) -> None:
        client = cls.get_client()
        client.cancel_payment(
            ecommerce_id=str(ecommerce_id),
        )

        # Update local record
        with transaction.atomic():
            try:
                payment = Payment.objects.select_for_update().get(
                    ecommerce_id=ecommerce_id
                )
                if payment.status not in (
                    Payment.Status.COMPLETED,
                    Payment.Status.CANCEL,
                ):
                    payment.status = Payment.Status.CANCEL
                    payment.save(update_fields=["status", "updated_at"])
            except Payment.DoesNotExist:
                pass

        logger.info("[django-athm] Cancelled payment %s", ecommerce_id)

    @classmethod
    def refund(
        cls,
        payment: Payment,
        amount: Decimal | None = None,
        message: str = "",
    ) -> Refund:
        if not payment.is_refundable:
            raise ValueError(
                f"[django-athm] Payment {payment.ecommerce_id} is not refundable"
            )

        if not payment.reference_number:
            raise ValueError(
                f"[django-athm] Payment {payment.ecommerce_id} has no reference number"
            )

        refund_amount = amount if amount is not None else payment.refundable_amount

        if refund_amount <= 0:
            raise ValueError("[django-athm] Refund amount must be positive")

        if refund_amount > payment.refundable_amount:
            raise ValueError(
                f"[django-athm] Refund amount {refund_amount} exceeds "
                f"refundable amount {payment.refundable_amount}"
            )

        client = cls.get_client()

        response = client.refund_payment(
            reference_number=payment.reference_number,
            amount=str(refund_amount),
            message=message[:50] if message else "",
        )

        logger.info(
            "[django-athm] Refunded $%s for payment %s",
            refund_amount,
            payment.ecommerce_id,
        )

        # Create local refund record
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment.pk)

            refund = Refund.objects.create(
                payment=payment,
                reference_number=response.data.refund.reference_number,
                daily_transaction_id=response.data.refund.daily_transaction_id or "",
                amount=refund_amount,
                message=message,
                status="COMPLETED",
                customer_name=response.data.refund.name or "",
                customer_phone=response.data.refund.phone_number or "",
                customer_email=response.data.refund.email or "",
                transaction_date=response.data.refund.date,
            )

            payment.total_refunded_amount += refund_amount
            payment.save(update_fields=["total_refunded_amount", "updated_at"])

        return refund

    # Remote status -> local status mapping
    _REMOTE_STATUS_MAP = {
        "CANCEL": Payment.Status.CANCEL,
        "EXPIRED": Payment.Status.EXPIRED,
        "expired": Payment.Status.EXPIRED,
        "CONFIRM": Payment.Status.CONFIRM,
    }

    @classmethod
    def sync_status(cls, payment: Payment) -> str:
        """
        Check remote status and update local payment if necessary.

        Returns:
            The current status (remote if updated, else local)
        """
        # If already in terminal state, no need to check
        if payment.status in (Payment.Status.COMPLETED, Payment.Status.CANCEL):
            return payment.status

        try:
            remote_status = cls.find_status(payment.ecommerce_id)
        except Exception as e:
            logger.warning("[django-athm] Failed to check remote status: %s", e)
            return payment.status

        if remote_status == payment.status:
            return payment.status

        new_status = cls._REMOTE_STATUS_MAP.get(remote_status)
        if not new_status:
            return payment.status

        # CONFIRM only allowed from OPEN
        if (
            new_status == Payment.Status.CONFIRM
            and payment.status != Payment.Status.OPEN
        ):
            return payment.status

        payment.status = new_status
        payment.save(update_fields=["status", "updated_at"])
        logger.info(
            "[django-athm] Payment %s status updated to %s",
            payment.ecommerce_id,
            new_status,
        )

        return payment.status
