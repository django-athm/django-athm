import hashlib
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone as django_timezone

from django_athm.models import Payment, PaymentLineItem, Refund, WebhookEvent
from django_athm.signals import payment_completed, payment_expired, payment_failed

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
    def process(cls, event: WebhookEvent) -> None:
        """
        Process a webhook event idempotently.

        Safe to call multiple times for the same event.

        Args:
            event: The WebhookEvent to process

        Raises:
            Exception: On processing failure (for retry handling)
        """
        if event.processed:
            logger.debug("[django-athm] Event %s already processed", event.id)
            return

        handler_name = cls.HANDLERS.get(str(event.event_type))
        if handler_name:
            handler = getattr(cls, handler_name)
            handler(event)
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
    def _parse_datetime(cls, value: Any) -> datetime | None:
        """Parse datetime from ATH Móvil format."""
        if not value:
            return None

        # Format: "2023-01-13 16:17:06" or timestamp
        if isinstance(value, str):
            try:
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                return django_timezone.make_aware(dt)
            except ValueError:
                pass

        # Try timestamp (milliseconds)
        try:
            val_int = int(value)
            # If > 1e10, assume milliseconds
            ts = val_int / 1000 if val_int > 1e10 else val_int
            return django_timezone.make_aware(datetime.fromtimestamp(ts))
        except (ValueError, TypeError, OSError):
            return None

    @classmethod
    def _get_locked_payment(
        cls, ecommerce_id: str, payload: dict
    ) -> tuple[Payment, bool]:
        """
        Get or create a payment record with row-level locking.
        """
        return Payment.objects.select_for_update().get_or_create(
            ecommerce_id=ecommerce_id,
            defaults={
                "status": Payment.Status.OPEN,
                "total": Decimal(str(payload.get("total", 0))),
                "subtotal": Decimal(str(payload.get("subTotal", 0))),
                "tax": Decimal(str(payload.get("tax", 0))),
                "metadata_1": payload.get("metadata1", ""),
                "metadata_2": payload.get("metadata2", ""),
            },
        )

    @classmethod
    def _get_payment_safe(
        cls, event: WebhookEvent
    ) -> tuple[Payment, bool] | tuple[None, None]:
        """
        Common helper to lock payment and check terminal state.

        Returns:
            (payment, created)
            or (None, None) if missing ecommerceId.
        """
        payload = event.payload
        ecommerce_id = payload.get("ecommerceId")

        if not ecommerce_id:
            logger.error("[django-athm] Missing ecommerceId in event %s", event.id)
            cls._mark_processed(event)
            return None, None

        payment, created = cls._get_locked_payment(ecommerce_id, payload)

        if created:
            logger.info("[django-athm] Created payment %s from webhook", ecommerce_id)

        return payment, created

    @staticmethod
    def _should_skip_update(payment: Payment, check_completed: bool = False) -> bool:
        """
        Check if we should skip updating this payment because it's already in a final state.
        Allows for idempotent reprocessing if calling with same state, but generally stops valid state transitions if invalid.
        """
        # If we are trying to set COMPLETED, check if already COMPLETED.
        if check_completed and payment.status == Payment.Status.COMPLETED:
            return True

        # If we are trying to CANCEL/EXPIRE, check if already in any terminal state.
        is_terminal = payment.status in (
            Payment.Status.COMPLETED,
            Payment.Status.CANCEL,
            Payment.Status.EXPIRED,
        )
        if not check_completed and is_terminal:
            return True

        return False

    @classmethod
    def _handle_ecommerce_completed(cls, event: WebhookEvent) -> None:
        """Handle completed ecommerce payment webhook."""
        with transaction.atomic():
            payment, _ = cls._get_payment_safe(event)
            if not payment:
                return

            # Idempotency: if already COMPLETED, skip.
            if cls._should_skip_update(payment, check_completed=True):
                logger.debug(
                    "[django-athm] Payment %s already completed", payment.ecommerce_id
                )
                cls._mark_processed(event, payment)
                return

            # Apply Updates
            payload = event.payload
            payment.reference_number = payload.get("referenceNumber", "")
            payment.daily_transaction_id = payload.get("dailyTransactionId", "")
            payment.fee = Decimal(str(payload.get("fee", 0)))
            payment.net_amount = Decimal(str(payload.get("netAmount", 0)))
            payment.total_refunded_amount = Decimal(
                str(payload.get("totalRefundedAmount", 0))
            )
            payment.customer_name = payload.get("name", "")
            payment.customer_phone = str(payload.get("phoneNumber", ""))
            payment.customer_email = payload.get("email", "")
            payment.message = payload.get("message", "")
            payment.business_name = payload.get("businessName", "")
            payment.transaction_date = cls._parse_datetime(
                payload.get("transactionDate") or payload.get("date")
            )

            payment.status = Payment.Status.COMPLETED
            payment.save()

            # Sync Items
            cls._sync_items(payment, payload.get("items", []))

            cls._mark_processed(event, payment)

            # Send Signals
            transaction.on_commit(
                lambda: payment_completed.send(sender=Payment, payment=payment)
            )

            logger.info(
                "[django-athm] Processed COMPLETED payment: %s", payment.ecommerce_id
            )

    @classmethod
    def _handle_ecommerce_cancelled(cls, event: WebhookEvent) -> None:
        """Handle cancelled ecommerce payment webhook."""
        with transaction.atomic():
            payment, _ = cls._get_payment_safe(event)
            if not payment:
                return

            # Idempotency: if already in ANY terminal state (CANCEL, EXPIRED, COMPLETED), skip.
            if cls._should_skip_update(payment, check_completed=False):
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
                lambda: payment_failed.send(
                    sender=Payment, payment=payment, reason="cancelled"
                )
            )

            logger.info(
                "[django-athm] Processed CANCEL payment: %s", payment.ecommerce_id
            )

    @classmethod
    def _handle_ecommerce_expired(cls, event: WebhookEvent) -> None:
        """Handle expired ecommerce payment webhook."""
        with transaction.atomic():
            payment, _ = cls._get_payment_safe(event)
            if not payment:
                return

            # Idempotency: skip if terminal
            if cls._should_skip_update(payment, check_completed=False):
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
    def _handle_refund(cls, event: WebhookEvent) -> None:
        """Handle refund webhook."""
        payload = event.payload
        reference_number = payload.get("referenceNumber")

        if not reference_number:
            logger.error(
                "[django-athm] Missing referenceNumber in refund event %s", event.id
            )
            cls._mark_processed(event)
            return

        with transaction.atomic():
            # Check if refund already exists (idempotency)
            if Refund.objects.filter(reference_number=reference_number).exists():
                logger.debug("[django-athm] Refund %s already exists", reference_number)
                cls._mark_processed(event)
                return

            # Attempt to link to a Payment via referenceNumber
            # "Refunds cannot be referenced to original payment" - documentation.
            # However, we allow strict linking if the referenceNumber happens to match a Payment.
            linked_payment = None
            try:
                linked_payment = Payment.objects.get(reference_number=reference_number)
            except Payment.DoesNotExist:
                logger.warning(
                    "[django-athm] Received refund %s but could not find matching Payment by referenceNumber",
                    reference_number,
                )

            # Create Refund record
            # Note: We need a 'payment' for the ForeignKey.
            # If we don't have a linked payment, we actually CANNOT create a Refund object due to foreign key constraint
            # unless the model allows null=True.
            # So if we can't link it, we log and skip.

            if linked_payment:
                Refund.objects.create(
                    payment=linked_payment,
                    reference_number=reference_number,
                    daily_transaction_id=payload.get("dailyTransactionId", ""),
                    amount=Decimal(
                        str(payload.get("amount", 0) or payload.get("total", 0))
                    ),  # Payload might vary
                    message=payload.get("message", ""),
                    status="COMPLETED",
                    customer_name=payload.get("name", ""),
                    customer_phone=str(payload.get("phoneNumber", "")),
                    customer_email=payload.get("email", ""),
                    transaction_date=cls._parse_datetime(
                        payload.get("transactionDate") or payload.get("date")
                    )
                    or django_timezone.now(),
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

    @classmethod
    def _handle_payment_received(cls, event: WebhookEvent) -> None:
        """Handle non-ecommerce payment (Pay a Business from app)."""
        logger.debug(
            "[django-athm] Ignoring non-ecommerce payment webhook %s",
            event.id,
        )
        cls._mark_processed(event)

    @classmethod
    def _handle_donation_received(cls, event: WebhookEvent) -> None:
        """Handle donation webhook."""
        logger.debug("[django-athm] Ignoring donation webhook %s", event.id)
        cls._mark_processed(event)

    @classmethod
    def _handle_simulated(cls, event: WebhookEvent) -> None:
        """Handle simulated/test webhook."""
        logger.info("[django-athm] Processing simulated event %s", event.id)
        cls._handle_ecommerce_completed(event)

    @classmethod
    def _sync_items(cls, payment: Payment, items: list) -> None:
        """Sync line items from webhook payload."""
        if not items:
            return

        # Only sync if we don't have items yet (ours take precedence)
        if payment.items.exists():
            return

        for item_data in items:
            PaymentLineItem.objects.create(
                transaction=payment,
                name=item_data.get("name", ""),
                description=item_data.get("description", ""),
                quantity=int(item_data.get("quantity", 1)),
                price=Decimal(str(item_data.get("price", 0))),
                tax=Decimal(str(item_data.get("tax", 0))),
                metadata=item_data.get("metadata", ""),
            )

        logger.debug(
            "[django-athm] Synced %d items for payment %s",
            len(items),
            payment.ecommerce_id,
        )
