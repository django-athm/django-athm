import hashlib
import logging
from decimal import Decimal

from athm.models import WebhookPayload
from django.db import IntegrityError, transaction
from django.utils import timezone as django_timezone

from django_athm.models import Payment, PaymentLineItem, Refund, WebhookEvent
from django_athm.signals import (
    payment_cancelled,
    payment_completed,
    payment_expired,
    refund_sent,
)

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """
    Processes webhook events from ATH Móvil idempotently with ACID guarantees.

    Handles de-duplication via idempotency keys, uses database transactions
    and row-level locking to prevent race conditions.
    """

    HANDLERS = {
        WebhookEvent.Type.ECOMMERCE_COMPLETED: "_handle_ecommerce_completed",
        WebhookEvent.Type.ECOMMERCE_CANCELLED: "_handle_ecommerce_cancelled",
        WebhookEvent.Type.ECOMMERCE_EXPIRED: "_handle_ecommerce_expired",
        WebhookEvent.Type.REFUND_SENT: "_handle_refund",
        WebhookEvent.Type.PAYMENT_RECEIVED: "_handle_payment_received",
        WebhookEvent.Type.DONATION_RECEIVED: "_handle_donation_received",
        WebhookEvent.Type.SIMULATED: "_handle_simulated",
    }

    @staticmethod
    def _compute_idempotency_key(payload: dict) -> str:
        """
        Derive a unique idempotency key from webhook payload.

        Different event types have different natural keys:
        - ecommerce events: ecommerceId + status
        - refunds: referenceNumber
        - payments/donations: transactionType + referenceNumber
        """
        event_type = WebhookProcessor._determine_event_type(payload)

        if str(event_type).startswith("ecommerce_"):
            parts = [
                payload.get("ecommerceId", ""),
                payload.get("status", ""),
            ]
        elif event_type == WebhookEvent.Type.REFUND_SENT:
            parts = ["refund", payload.get("referenceNumber", "")]
        else:
            parts = [
                payload.get("transactionType", ""),
                payload.get("referenceNumber", ""),
            ]

        key_string = ":".join(str(p) for p in parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    @staticmethod
    def _determine_event_type(payload: dict) -> str:
        """Determine event type from webhook payload structure."""
        tx_type = str(payload.get("transactionType", "")).lower()
        status = str(payload.get("status", "")).upper()

        # eCommerce events have ecommerceId field
        if "ecommerceId" in payload or tx_type == "ecommerce":
            if status == "COMPLETED":
                return WebhookEvent.Type.ECOMMERCE_COMPLETED
            elif status == "CANCEL":
                return WebhookEvent.Type.ECOMMERCE_CANCELLED
            elif status in ("EXPIRED", "expired"):
                return WebhookEvent.Type.ECOMMERCE_EXPIRED
            return WebhookEvent.Type.UNKNOWN

        if tx_type == "refund":
            return WebhookEvent.Type.REFUND_SENT
        if tx_type == "payment":
            return WebhookEvent.Type.PAYMENT_RECEIVED
        if tx_type == "donation":
            return WebhookEvent.Type.DONATION_RECEIVED
        if tx_type == "simulated":
            return WebhookEvent.Type.SIMULATED

        return WebhookEvent.Type.UNKNOWN

    @classmethod
    def store_event(
        cls,
        payload: dict,
        remote_ip: str | None = None,
    ) -> tuple[WebhookEvent, bool]:
        """
        Store a webhook event, handling duplicates via idempotency key.

        Args:
            payload: The raw webhook payload dict
            remote_ip: IP address of the request

        Returns:
            Tuple of (WebhookEvent, created).
            If created=False, this is a duplicate event.
        """
        idempotency_key = cls._compute_idempotency_key(payload)
        event_type = cls._determine_event_type(payload)

        try:
            event = WebhookEvent.objects.create(
                idempotency_key=idempotency_key,
                event_type=event_type,
                payload=payload,
                remote_ip=remote_ip,
            )
            logger.debug("[django-athm] Stored webhook event %s", event.id)
            return event, True
        except IntegrityError:
            # Duplicate - fetch existing
            event = WebhookEvent.objects.get(idempotency_key=idempotency_key)
            logger.debug("[django-athm] Duplicate webhook event %s", idempotency_key)
            return event, False

    @classmethod
    def process(cls, event: WebhookEvent, normalized: WebhookPayload) -> None:
        """
        Process a webhook event idempotently.

        Safe to call multiple times for the same event.

        Args:
            event: The WebhookEvent to process
            normalized: Validated and normalized webhook payload from parse_webhook

        Raises:
            Exception: On processing failure (for retry handling)
        """
        if event.processed:
            logger.debug("[django-athm] Event %s already processed", event.id)
            return

        handler_name = cls.HANDLERS.get(str(event.event_type))
        if handler_name:
            handler = getattr(cls, handler_name)
            handler(event, normalized)
        else:
            logger.warning(
                "[django-athm] No handler for event type: %s", event.event_type
            )
            cls._mark_processed(event)

    @classmethod
    def _mark_processed(
        cls,
        event: WebhookEvent,
        payment: Payment | None = None,
    ) -> None:
        """Mark event as processed and optionally link to payment."""
        event.processed = True
        event.transaction = payment
        event.save(update_fields=["processed", "transaction", "modified"])

    @classmethod
    def mark_processed(cls, event: WebhookEvent) -> None:
        """
        Public method to mark event as processed (for view error handling).

        Args:
            event: The WebhookEvent to mark as processed
        """
        cls._mark_processed(event)

    @classmethod
    def _get_locked_payment(
        cls, ecommerce_id: str, normalized: WebhookPayload
    ) -> tuple[Payment, bool]:
        """
        Get or create a payment record with row-level locking.

        Args:
            ecommerce_id: The ecommerce transaction ID
            normalized: Normalized WebhookPayload object from parse_webhook
        """
        return Payment.objects.select_for_update().get_or_create(
            ecommerce_id=ecommerce_id,
            defaults={
                "status": Payment.Status.OPEN,
                "total": normalized.total or Decimal("0"),
                "subtotal": normalized.subtotal or Decimal("0"),
                "tax": normalized.tax or Decimal("0"),
                "metadata_1": normalized.metadata1 or "",
                "metadata_2": normalized.metadata2 or "",
            },
        )

    @classmethod
    def _get_payment_safe(
        cls, event: WebhookEvent, normalized: WebhookPayload
    ) -> tuple[Payment, bool] | tuple[None, None]:
        """
        Common helper to lock payment and check terminal state.

        Args:
            event: The webhook event being processed
            normalized: Normalized WebhookPayload object from parse_webhook

        Returns:
            (payment, created)
            or (None, None) if missing ecommerce_id.
        """
        ecommerce_id = normalized.ecommerce_id

        if not ecommerce_id:
            logger.error("[django-athm] Missing ecommerce_id in event %s", event.id)
            cls._mark_processed(event)
            return None, None

        payment, created = cls._get_locked_payment(ecommerce_id, normalized)

        if created:
            logger.info("[django-athm] Created payment %s from webhook", ecommerce_id)

        return payment, created

    TERMINAL_STATUSES = (
        Payment.Status.COMPLETED,
        Payment.Status.CANCEL,
        Payment.Status.EXPIRED,
    )

    @staticmethod
    def _is_already_completed(payment: Payment) -> bool:
        """Check if payment is already completed (for idempotent completion)."""
        return payment.status == Payment.Status.COMPLETED

    @classmethod
    def _is_terminal(cls, payment: Payment) -> bool:
        """Check if payment is in any terminal state."""
        return payment.status in cls.TERMINAL_STATUSES

    @classmethod
    def _handle_ecommerce_completed(
        cls, event: WebhookEvent, normalized: WebhookPayload
    ) -> None:
        """Handle completed ecommerce payment webhook."""
        with transaction.atomic():
            payment, _ = cls._get_payment_safe(event, normalized)
            if not payment:
                return

            # Idempotency: if already COMPLETED, skip.
            if cls._is_already_completed(payment):
                logger.debug(
                    "[django-athm] Payment %s already completed", payment.ecommerce_id
                )
                cls._mark_processed(event, payment)
                return

            # Apply Updates (using normalized snake_case fields)
            payment.reference_number = normalized.reference_number or ""
            payment.daily_transaction_id = normalized.daily_transaction_id or ""
            payment.fee = normalized.fee or Decimal("0")
            payment.net_amount = normalized.net_amount or Decimal("0")
            payment.total_refunded_amount = normalized.total_refunded_amount or Decimal(
                "0"
            )
            payment.customer_name = normalized.name or ""
            payment.customer_phone = normalized.phone_number or ""
            payment.customer_email = normalized.email or ""
            payment.message = normalized.message or ""
            payment.business_name = normalized.business_name or ""
            payment.transaction_date = (
                django_timezone.make_aware(normalized.transaction_date)
                if normalized.transaction_date
                and normalized.transaction_date.tzinfo is None
                else normalized.transaction_date
            )

            payment.status = Payment.Status.COMPLETED
            payment.save()

            # Sync Items
            cls._sync_items(payment, normalized.items)

            cls._mark_processed(event, payment)

            # Send Signals
            transaction.on_commit(
                lambda: payment_completed.send(sender=Payment, payment=payment)
            )

            logger.info(
                "[django-athm] Processed COMPLETED payment: %s", payment.ecommerce_id
            )

    @classmethod
    def _handle_ecommerce_cancelled(
        cls, event: WebhookEvent, normalized: WebhookPayload
    ) -> None:
        """Handle cancelled ecommerce payment webhook."""
        with transaction.atomic():
            payment, _ = cls._get_payment_safe(event, normalized)
            if not payment:
                return

            # Idempotency: if already in terminal state, skip.
            if cls._is_terminal(payment):
                logger.debug(
                    "[django-athm] Payment %s already in terminal state %s",
                    payment.ecommerce_id,
                    payment.status,
                )
                cls._mark_processed(event, payment)
                return

            payment.status = Payment.Status.CANCEL
            payment.save()

            cls._mark_processed(event, payment)

            transaction.on_commit(
                lambda: payment_cancelled.send(sender=Payment, payment=payment)
            )

            logger.info(
                "[django-athm] Processed CANCEL payment: %s", payment.ecommerce_id
            )

    @classmethod
    def _handle_ecommerce_expired(
        cls, event: WebhookEvent, normalized: WebhookPayload
    ) -> None:
        """Handle expired ecommerce payment webhook."""
        with transaction.atomic():
            payment, _ = cls._get_payment_safe(event, normalized)
            if not payment:
                return

            # Idempotency: skip if terminal
            if cls._is_terminal(payment):
                logger.debug(
                    "[django-athm] Payment %s already in terminal state %s",
                    payment.ecommerce_id,
                    payment.status,
                )
                cls._mark_processed(event, payment)
                return

            payment.status = Payment.Status.EXPIRED
            payment.save()

            cls._mark_processed(event, payment)

            transaction.on_commit(
                lambda: payment_expired.send(sender=Payment, payment=payment)
            )

            logger.info(
                "[django-athm] Processed EXPIRED payment: %s", payment.ecommerce_id
            )

    @classmethod
    def _handle_refund(cls, event: WebhookEvent, normalized: WebhookPayload) -> None:
        """Handle refund webhook."""
        reference_number = normalized.reference_number

        if not reference_number:
            logger.error(
                "[django-athm] Missing reference_number in refund event %s", event.id
            )
            cls._mark_processed(event)
            return

        with transaction.atomic():
            # Check if refund already exists (idempotency)
            if Refund.objects.filter(reference_number=reference_number).exists():
                logger.debug("[django-athm] Refund %s already exists", reference_number)
                cls._mark_processed(event)
                return

            # Attempt to link to a Payment via reference_number
            # "Refunds cannot be referenced to original payment" - documentation.
            # However, we allow strict linking if the reference_number happens to match a Payment.
            linked_payment = None
            try:
                linked_payment = Payment.objects.get(reference_number=reference_number)
            except Payment.DoesNotExist:
                logger.warning(
                    "[django-athm] Received refund %s but could not find matching Payment by reference_number",
                    reference_number,
                )

            # Create Refund record
            # Note: We need a 'payment' for the ForeignKey.
            # If we don't have a linked payment, we actually CANNOT create a Refund object due to foreign key constraint
            # unless the model allows null=True.
            # So if we can't link it, we log and skip.

            if linked_payment:
                transaction_date = normalized.transaction_date or normalized.date
                Refund.objects.create(
                    payment=linked_payment,
                    reference_number=reference_number,
                    daily_transaction_id=normalized.daily_transaction_id or "",
                    amount=normalized.total or Decimal("0"),
                    message=normalized.message or "",
                    status="COMPLETED",
                    customer_name=normalized.name or "",
                    customer_phone=normalized.phone_number or "",
                    customer_email=normalized.email or "",
                    transaction_date=(
                        django_timezone.make_aware(transaction_date)
                        if transaction_date and transaction_date.tzinfo is None
                        else transaction_date or django_timezone.now()
                    ),
                )
                logger.info(
                    "[django-athm] Recorded refund %s linked to payment %s",
                    reference_number,
                    linked_payment.reference_number,
                )
            else:
                logger.info(
                    "[django-athm] Skipped storing Refund %s because no linked Payment was found.",
                    reference_number,
                )

            cls._mark_processed(event, linked_payment)

            # Send signal only if refund was created
            if linked_payment:
                refund = Refund.objects.get(reference_number=reference_number)
                transaction.on_commit(
                    lambda: refund_sent.send(
                        sender=Refund, refund=refund, payment=linked_payment
                    )
                )

    @classmethod
    def _handle_payment_received(
        cls, event: WebhookEvent, normalized: WebhookPayload
    ) -> None:
        """Handle non-ecommerce payment (Pay a Business from app)."""
        logger.debug(
            "[django-athm] Ignoring non-ecommerce payment webhook %s",
            event.id,
        )
        cls._mark_processed(event)

    @classmethod
    def _handle_donation_received(
        cls, event: WebhookEvent, normalized: WebhookPayload
    ) -> None:
        """Handle donation webhook."""
        logger.debug("[django-athm] Ignoring donation webhook %s", event.id)
        cls._mark_processed(event)

    @classmethod
    def _handle_simulated(cls, event: WebhookEvent, normalized: WebhookPayload) -> None:
        """Handle simulated/test webhook."""
        logger.info("[django-athm] Processing simulated event %s", event.id)
        cls._handle_ecommerce_completed(event, normalized)

    @classmethod
    def _sync_items(cls, payment: Payment, items: list) -> None:
        """Sync line items from webhook payload.

        Args:
            payment: The payment to sync items to
            items: List of WebhookItem objects from normalized payload
        """
        if not items:
            return

        # Only sync if we don't have items yet (ours take precedence)
        if payment.items.exists():
            return

        for item in items:
            PaymentLineItem.objects.create(
                transaction=payment,
                name=item.name,
                description=item.description,
                quantity=item.quantity,
                price=item.price,
                tax=item.tax or Decimal("0"),
                metadata=item.metadata or "",
            )

        logger.debug(
            "[django-athm] Synced %d items for payment %s",
            len(items),
            payment.ecommerce_id,
        )
