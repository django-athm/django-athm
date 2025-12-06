import uuid
from decimal import Decimal

import phonenumbers
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django_athm.exceptions import ATHM_RefundError

from .conf import settings
from .constants import REFUND_URL, REPORT_URL, SEARCH_URL, TransactionStatus
from .utils import get_http_adapter


def validate_phone_number(value):
    parsed_number = phonenumbers.parse(value, "US")

    if not phonenumbers.is_valid_number(parsed_number):
        raise ValidationError(
            f"{value} is ",
            params={"value": value},
        )


class ATHM_Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=512)
    email = models.EmailField(max_length=254, blank=True)
    phone_number = models.CharField(
        max_length=32, blank=True, validators=[validate_phone_number]
    )

    class Meta:
        verbose_name = _("ATH Móvil Client")
        verbose_name_plural = _("ATH Móvil Clients")

    def __str__(self):
        return self.name


class ATHM_Transaction(models.Model):
    """
    Represents an ATH Móvil payment transaction.

    Tracks the full lifecycle of a payment from creation through completion,
    cancellation, or refund. Can be created via webhooks or API sync.
    """

    class Status(models.TextChoices):
        """Transaction status choices matching ATH Móvil API states."""
        OPEN = "open", _("Open")
        CONFIRM = "confirm", _("Confirmed")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")
        EXPIRED = "expired", _("Expired")
        REFUNDED = "refunded", _("Refunded")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Transaction identifiers
    reference_number = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text=_("ATH Móvil reference number for completed transactions")
    )
    ecommerce_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text=_("Unique ecommerce transaction identifier")
    )
    daily_transaction_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text=_("ATH Móvil daily transaction ID")
    )

    # Status and timing
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    date = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("Transaction completion date from ATH Móvil")
    )
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    # Monetary amounts - using DecimalField for precision
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Total transaction amount")
    )
    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Tax amount")
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Subtotal before tax")
    )
    fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("ATH Móvil processing fee")
    )
    refunded_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Amount refunded")
    )

    # Customer information
    customer_name = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Customer name from ATH Móvil")
    )
    customer_phone = models.CharField(
        max_length=32,
        blank=True,
        help_text=_("Customer phone number")
    )

    # Business information
    business_name = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Business name from ATH Móvil")
    )

    # Metadata
    message = models.CharField(max_length=512, blank=True, null=True)
    metadata_1 = models.CharField(max_length=64, blank=True, null=True)
    metadata_2 = models.CharField(max_length=64, blank=True, null=True)

    # Relationships
    client = models.ForeignKey(
        ATHM_Client,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
        related_query_name="transaction",
    )

    class Meta:
        verbose_name = _("ATH Móvil Transaction")
        verbose_name_plural = _("ATH Móvil Transactions")
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["-created"]),
            models.Index(fields=["status", "-created"]),
        ]

    def __str__(self):
        if self.reference_number:
            return self.reference_number
        return str(self.ecommerce_id or self.id)

    http_adapter = get_http_adapter()

    @property
    def net_amount(self):
        """Calculate net amount after fees."""
        if not self.fee:
            return self.total
        return self.total - self.fee

    @property
    def is_refundable(self):
        """Check if transaction can be refunded."""
        return self.status == self.Status.COMPLETED and (
            not self.refunded_amount or self.refunded_amount < self.total
        )

    @property
    def is_complete(self):
        """Check if transaction is completed."""
        return self.status == self.Status.COMPLETED

    @classmethod
    def get_report(cls, start_date, end_date, public_token=None, private_token=None):
        if not public_token:
            public_token = settings.PUBLIC_TOKEN

        if not private_token:
            private_token = settings.PRIVATE_TOKEN

        response = cls.http_adapter.get_with_data(
            url=REPORT_URL,
            data=dict(
                publicToken=public_token,
                privateToken=private_token,
                fromDate=start_date,
                toDate=end_date,
            ),
        )

        return response

    @classmethod
    def refund(cls, transaction, amount=None):
        """
        Refund a transaction.

        Args:
            transaction: The ATHM_Transaction to refund
            amount: Amount to refund (defaults to full transaction amount)

        Returns:
            dict: API response

        Raises:
            ATHM_RefundError: If refund fails
        """
        # Refund the whole transaction by default
        if not amount:
            amount = transaction.total

        # Convert Decimal to string for API
        amount_str = str(amount)

        response = cls.http_adapter.post(
            REFUND_URL,
            data=dict(
                publicToken=settings.PUBLIC_TOKEN,
                privateToken=settings.PRIVATE_TOKEN,
                referenceNumber=transaction.reference_number,
                amount=amount_str,
            ),
        ).json()

        if "errorCode" in response:
            raise ATHM_RefundError(response.get("description"))

        # Update the transaction status if refund was successful
        if response.get("refundStatus") == TransactionStatus.completed.value:
            transaction.status = cls.Status.REFUNDED
            transaction.refunded_amount = Decimal(str(response.get("refundedAmount", amount)))
            transaction.save(update_fields=["status", "refunded_amount", "modified"])

        return response

    @classmethod
    def search(cls, transaction):
        response = cls.http_adapter.post(
            SEARCH_URL,
            data=dict(
                publicToken=settings.PUBLIC_TOKEN,
                privateToken=settings.PRIVATE_TOKEN,
                referenceNumber=transaction.reference_number,
            ),
        )

        return response.json()


class ATHM_Item(models.Model):
    """Line item associated with an ATH Móvil transaction."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        ATHM_Transaction,
        on_delete=models.CASCADE,
        related_name="items",
        related_query_name="item",
    )

    name = models.CharField(max_length=128, help_text=_("Item name"))
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Item description")
    )
    quantity = models.PositiveSmallIntegerField(default=1)

    # Using DecimalField for precision
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Item price")
    )
    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Item tax")
    )
    metadata = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        verbose_name = _("ATH Móvil Item")
        verbose_name_plural = _("ATH Móvil Items")

    def __str__(self):
        return self.name


class ATHM_WebhookEvent(models.Model):
    """
    Tracks webhook events received from ATH Móvil.

    Similar to dj-stripe's WebhookEventTrigger, this model records all
    incoming webhook requests for auditing and debugging purposes.
    """

    class EventType(models.TextChoices):
        PAYMENT_RECEIVED = "payment_received", _("Payment Received")
        DONATION_RECEIVED = "donation_received", _("Donation Received")
        REFUND_SENT = "refund_sent", _("Refund Sent")
        ECOMMERCE_COMPLETED = "ecommerce_completed", _("eCommerce Payment Completed")
        ECOMMERCE_CANCELLED = "ecommerce_cancelled", _("eCommerce Payment Cancelled")
        ECOMMERCE_EXPIRED = "ecommerce_expired", _("eCommerce Payment Expired")
        UNKNOWN = "unknown", _("Unknown")

    id = models.BigAutoField(primary_key=True)

    # Request metadata
    remote_ip = models.GenericIPAddressField(
        help_text=_("IP address of the webhook request")
    )
    headers = models.JSONField(
        default=dict,
        help_text=_("HTTP headers from the webhook request")
    )
    body = models.TextField(help_text=_("Raw webhook payload"))

    # Processing state
    valid = models.BooleanField(
        default=False,
        help_text=_("Whether the webhook passed validation")
    )
    processed = models.BooleanField(
        default=False,
        help_text=_("Whether the webhook was successfully processed")
    )

    # Event details
    event_type = models.CharField(
        max_length=32,
        choices=EventType.choices,
        default=EventType.UNKNOWN,
        help_text=_("Type of webhook event")
    )
    transaction_status = models.CharField(
        max_length=16,
        blank=True,
        help_text=_("Transaction status from webhook")
    )

    # Error tracking
    exception = models.CharField(max_length=255, blank=True)
    traceback = models.TextField(blank=True)

    # Relationships
    transaction = models.ForeignKey(
        ATHM_Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_events",
        help_text=_("Associated transaction if found/created")
    )

    # Timestamps
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("ATH Móvil Webhook Event")
        verbose_name_plural = _("ATH Móvil Webhook Events")
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["-created"]),
            models.Index(fields=["valid", "processed"]),
        ]

    def __str__(self):
        return f"Webhook {self.id} - {self.event_type} (valid={self.valid}, processed={self.processed})"
