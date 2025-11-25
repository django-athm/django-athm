import uuid

import phonenumbers
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_athm.exceptions import ATHM_RefundError

from .conf import settings
from .constants import (
    CANCEL_PAYMENT_URL,
    FIND_PAYMENT_URL,
    REFUND_URL,
    REPORT_URL,
    SEARCH_URL,
    TransactionStatus,
)
from .utils import get_http_adapter


def validate_phone_number(value):
    parsed_number = phonenumbers.parse(value, "US")

    if not phonenumbers.is_valid_number(parsed_number):
        raise ValidationError(
            f"{value} is not a valid US phone number",
            params={"value": value},
        )


class ATHM_ClientQuerySet(models.QuerySet):
    """Custom QuerySet for ATHM_Client with common queries."""

    def with_transactions(self):
        """Return clients with their related transactions prefetched."""
        return self.prefetch_related("transactions")


class ATHM_ClientManager(models.Manager):
    """Custom manager for ATHM_Client model."""

    def get_queryset(self):
        return ATHM_ClientQuerySet(self.model, using=self._db)

    def with_transactions(self):
        return self.get_queryset().with_transactions()


class ATHM_Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=512)
    email = models.EmailField(max_length=254, blank=True)
    phone_number = models.CharField(
        max_length=32, blank=True, validators=[validate_phone_number]
    )

    objects = ATHM_ClientManager()

    class Meta:
        verbose_name = _("ATH Móvil Client")
        verbose_name_plural = _("ATH Móvil Clients")

    def __str__(self):
        return self.name


class ATHM_TransactionQuerySet(models.QuerySet):
    """Custom QuerySet for ATHM_Transaction with common queries."""

    def completed(self):
        """Return only completed transactions."""
        return self.filter(status=ATHM_Transaction.Status.COMPLETED)

    def refundable(self):
        """Return transactions that can be refunded (completed and not already refunded)."""
        return self.filter(
            status=ATHM_Transaction.Status.COMPLETED,
            refunded_amount__isnull=True,
        )

    def refunded(self):
        """Return refunded transactions."""
        return self.filter(status=ATHM_Transaction.Status.REFUNDED)

    def pending(self):
        """Return pending transactions (OPEN or CONFIRM status)."""
        return self.filter(
            status__in=[ATHM_Transaction.Status.OPEN, ATHM_Transaction.Status.CONFIRM]
        )

    def with_items(self):
        """Return transactions with their related items prefetched."""
        return self.prefetch_related("items")

    def with_client(self):
        """Return transactions with their related client."""
        return self.select_related("client")

    def by_date_range(self, start_date, end_date):
        """Filter transactions by date range."""
        return self.filter(date__gte=start_date, date__lte=end_date)


class ATHM_TransactionManager(models.Manager):
    """Custom manager for ATHM_Transaction model."""

    def get_queryset(self):
        return ATHM_TransactionQuerySet(self.model, using=self._db)

    def completed(self):
        return self.get_queryset().completed()

    def refundable(self):
        return self.get_queryset().refundable()

    def refunded(self):
        return self.get_queryset().refunded()

    def pending(self):
        return self.get_queryset().pending()

    def with_items(self):
        return self.get_queryset().with_items()

    def with_client(self):
        return self.get_queryset().with_client()

    def by_date_range(self, start_date, end_date):
        return self.get_queryset().by_date_range(start_date, end_date)


class ATHM_Transaction(models.Model):
    # NOTE: different from the API's status values
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        CONFIRM = "confirm", _("Confirm")
        COMPLETED = "completed", _("Completed")
        CANCEL = "cancel", _("Cancel")
        REFUNDED = "refunded", _("Refunded")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(unique=True, max_length=64)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
    )

    date = models.DateTimeField(blank=True)

    total = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    message = models.CharField(max_length=512, blank=True, null=True)
    metadata_1 = models.CharField(
        max_length=40, blank=True, null=True, help_text=_("Max 40 characters")
    )
    metadata_2 = models.CharField(
        max_length=40, blank=True, null=True, help_text=_("Max 40 characters")
    )

    # ATH Móvil v4 API fields
    ecommerce_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        db_index=True,
        help_text=_("ATH Móvil eCommerce transaction ID"),
    )
    ecommerce_status = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text=_("Status from ATH Móvil API"),
    )
    customer_name = models.CharField(
        max_length=256,
        blank=True,
        null=True,
        help_text=_("Customer name from ATH Móvil account"),
    )
    customer_phone = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text=_("Customer phone from ATH Móvil account"),
    )
    net_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Net amount after fees"),
    )

    client = models.ForeignKey(
        ATHM_Client,
        null=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
        related_query_name="transaction",
    )

    objects = ATHM_TransactionManager()

    class Meta:
        verbose_name = _("ATH Móvil Transaction")
        verbose_name_plural = _("ATH Móvil Transactions")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["-date"]),
            models.Index(fields=["status", "-date"]),
        ]

    def __str__(self):
        return self.reference_number

    @property
    def is_refundable(self):
        """Check if transaction can be refunded."""
        return self.status == self.Status.COMPLETED and self.refunded_amount is None

    @property
    def is_completed(self):
        """Check if transaction is completed."""
        return self.status == self.Status.COMPLETED

    @property
    def is_pending(self):
        """Check if transaction is pending."""
        return self.status in [self.Status.OPEN, self.Status.CONFIRM]

    http_adapter = get_http_adapter()

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
        # Refund the whole transaction by default
        if not amount:
            amount = transaction.total

        response = cls.http_adapter.post(
            REFUND_URL,
            data=dict(
                publicToken=settings.PUBLIC_TOKEN,
                privateToken=settings.PRIVATE_TOKEN,
                referenceNumber=transaction.reference_number,
                amount=str(amount),
            ),
        )

        if "errorCode" in response:
            raise ATHM_RefundError(response.get("description"))

        # Update the transaction status if refund was successful
        if response["refundStatus"] == TransactionStatus.completed.value:
            transaction.status = cls.Status.REFUNDED
            transaction.refunded_amount = response["refundedAmount"]
            transaction.save()

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

        return response

    @classmethod
    def find_payment(cls, ecommerce_id, public_token=None):
        """
        Find payment using ATH Móvil v4 API.

        Args:
            ecommerce_id: The eCommerce transaction ID from ATH Móvil
            public_token: Optional public token (uses settings if not provided)

        Returns:
            dict: API response with transaction details
        """
        if not public_token:
            public_token = settings.PUBLIC_TOKEN

        response = cls.http_adapter.post(
            FIND_PAYMENT_URL,
            data=dict(ecommerceId=ecommerce_id, publicToken=public_token),
        )

        return response

    @classmethod
    def cancel_payment(cls, ecommerce_id, public_token=None):
        """
        Cancel payment using ATH Móvil v4 API.

        Args:
            ecommerce_id: The eCommerce transaction ID from ATH Móvil
            public_token: Optional public token (uses settings if not provided)

        Returns:
            dict: API response with cancellation details
        """
        if not public_token:
            public_token = settings.PUBLIC_TOKEN

        response = cls.http_adapter.post(
            CANCEL_PAYMENT_URL,
            data=dict(ecommerceId=ecommerce_id, publicToken=public_token),
        )

        return response


class ATHM_Item(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        ATHM_Transaction,
        on_delete=models.CASCADE,
        related_name="items",
        related_query_name="item",
    )

    name = models.CharField(max_length=32)
    description = models.CharField(max_length=128)
    quantity = models.PositiveSmallIntegerField(default=1)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    metadata = models.CharField(
        max_length=40, blank=True, null=True, help_text=_("Max 40 characters")
    )

    class Meta:
        verbose_name = _("ATH Móvil Item")
        verbose_name_plural = _("ATH Móvil Items")

    def __str__(self):
        return self.name
