import uuid
from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _


class Payment(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", _("Open (Pending Customer Confirmation)")
        CONFIRM = "CONFIRM", _("Confirmed (Pending Authorization)")
        COMPLETED = "COMPLETED", _("Completed")
        CANCEL = "CANCEL", _("Cancelled")
        EXPIRED = "EXPIRED", _("Expired")

    # Terminal statuses where no further state transitions are expected
    TERMINAL_STATUSES = (Status.COMPLETED, Status.CANCEL, Status.EXPIRED)

    # Primary identifier from ATH Móvil
    ecommerce_id = models.UUIDField(
        primary_key=True,
        help_text=_("Unique ecommerce transaction identifier"),
    )

    # Upstream transaction identifiers (populated on completion)
    reference_number = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        help_text=_("ATH Móvil reference number for completed transactions"),
    )
    daily_transaction_id = models.CharField(
        max_length=10,
        blank=True,
        help_text=_("ATH Móvil daily transaction ID"),
    )

    # Status and timing
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    transaction_date = models.DateTimeField(
        blank=True, null=True, help_text=_("Transaction completion date from ATH Móvil")
    )

    # Monetary amounts (using DecimalField for precision)
    total = models.DecimalField(
        max_digits=10, decimal_places=2, help_text=_("Total transaction amount")
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Subtotal before tax"),
    )
    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Tax amount"),
    )
    fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("ATH Móvil processing fee"),
    )
    net_amount = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Amount after possible fees"),
    )
    total_refunded_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Amount refunded"),
    )

    # Customer information at the time of payment
    customer_name = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Customer name from ATH Móvil at the time of payment"),
    )
    customer_phone = models.CharField(
        max_length=32,
        blank=True,
        help_text=_("Customer phone number from ATH Móvil at the time of payment"),
    )
    customer_email = models.EmailField(
        blank=True,
        help_text=_("Customer email address from ATH Móvil at the time of payment"),
    )

    client = models.ForeignKey(
        "Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        help_text=_("Associated client record"),
    )

    # Metadata
    metadata_1 = models.CharField(max_length=64, blank=True, null=True)
    metadata_2 = models.CharField(max_length=64, blank=True, null=True)

    message = models.TextField(blank=True, null=True)
    business_name = models.CharField(
        max_length=255, blank=True, help_text=_("Business name from ATH Móvil")
    )

    class Meta:
        db_table = "athm_payment"
        verbose_name = _("ATH Móvil Transaction")
        verbose_name_plural = _("ATH Móvil Transactions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="athm_payment_created_idx"),
            models.Index(
                fields=["status", "-created_at"], name="athm_payment_status_idx"
            ),
            models.Index(fields=["reference_number"], name="athm_payment_ref_idx"),
        ]

    def __str__(self):
        if self.reference_number:
            return self.reference_number
        return str(self.ecommerce_id)

    @property
    def is_successful(self) -> bool:
        return self.status == self.Status.COMPLETED

    @property
    def is_refundable(self) -> bool:
        return self.is_successful and self.total > self.total_refunded_amount

    @property
    def refundable_amount(self) -> Decimal:
        if not self.is_refundable:
            return Decimal("0.00")
        return self.total - self.total_refunded_amount


class Refund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, related_name="refunds"
    )

    reference_number = models.CharField(max_length=255, unique=True)
    daily_transaction_id = models.CharField(
        max_length=10,
        blank=True,
        help_text=_("ATH Móvil daily transaction ID"),
    )

    amount = models.DecimalField(max_digits=7, decimal_places=2)
    message = models.CharField(max_length=50, blank=True)

    status = models.CharField(max_length=20, default="COMPLETED")

    # Customer info at time of refund
    customer_name = models.CharField(max_length=255, blank=True)
    customer_phone = models.CharField(max_length=32, blank=True)
    customer_email = models.EmailField(blank=True)

    client = models.ForeignKey(
        "Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refunds",
        help_text=_("Associated client record"),
    )

    transaction_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "athm_refund"
        verbose_name = _("ATH Móvil Refund")
        verbose_name_plural = _("ATH Móvil Refunds")


class WebhookEvent(models.Model):
    """
    Tracks webhook events received from ATH Móvil.
    """

    class Type(models.TextChoices):
        SIMULATED = "simulated", _("Payment Simulation")
        PAYMENT_RECEIVED = "payment", _("Payment Received")
        DONATION_RECEIVED = "donation", _("Donation Received")
        REFUND_SENT = "refund", _("Refund Sent")
        ECOMMERCE_COMPLETED = "ecommerce_completed", _("eCommerce Payment Completed")
        ECOMMERCE_CANCELLED = "ecommerce_cancelled", _("eCommerce Payment Cancelled")
        ECOMMERCE_EXPIRED = "ecommerce_expired", _("eCommerce Payment Expired")
        UNKNOWN = "unknown", _("Unknown")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Idempotency key derived from payload
    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True)

    # Event details
    event_type = models.CharField(
        max_length=64,
        choices=Type.choices,
        default=Type.UNKNOWN,
        help_text=_("Type of webhook event"),
    )

    # Request metadata
    remote_ip = models.GenericIPAddressField(
        help_text=_("IP address of the webhook request")
    )

    # The raw JSON payload
    payload = models.JSONField()

    # Processing state
    processed = models.BooleanField(
        default=False, help_text=_("Whether the webhook was successfully processed")
    )

    # Relationships
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_events",
        help_text=_("Associated payment if found/created"),
    )
    refund = models.ForeignKey(
        Refund,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_events",
        help_text=_("Associated refund for refund webhooks"),
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "athm_webhook_event"
        verbose_name = _("ATH Móvil Webhook Event")
        verbose_name_plural = _("ATH Móvil Webhook Events")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="athm_webhook_created_idx"),
            models.Index(
                fields=["event_type", "processed"], name="athm_webhook_type_idx"
            ),
        ]

    def __str__(self):
        status = "processed" if self.processed else "pending"
        return f"{self.event_type} ({status})"


class Client(models.Model):
    """
    ATH Movil customer record linked by phone number.

    Represents a unique customer identified by their normalized phone number.
    Name and email are updated with latest information from webhook events.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    phone_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_("Phone number (normalized to digits only)"),
    )

    name = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Customer name (updated from latest transaction)"),
    )

    email = models.EmailField(
        blank=True,
        help_text=_("Customer email (updated from latest transaction)"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "athm_client"
        verbose_name = _("ATH Movil Client")
        verbose_name_plural = _("ATH Movil Clients")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="athm_client_created_idx"),
        ]

    def __str__(self):
        if self.name:
            return f"{self.name} ({self.phone_number})"
        return self.phone_number
