import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from django_athm.exceptions import ATHM_RefundError

from .conf import settings
from .constants import COMPLETED_STATUS, LIST_URL, REFUND_URL, STATUS_URL
from .utils import get_http_adapter


class ATHM_Transaction(models.Model):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"

    TRANSACTION_STATUS_CHOICES = [
        (PROCESSING, "processing"),
        (COMPLETED, "completed"),
        (REFUNDED, "refunded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(unique=True, max_length=64)
    status = models.CharField(
        max_length=16, choices=TRANSACTION_STATUS_CHOICES, default=PROCESSING
    )

    # TODO: Use ATH Móvil's date from .inspect()
    date = models.DateTimeField(auto_now_add=True)

    total = models.FloatField()
    tax = models.FloatField(null=True)
    refunded_amount = models.FloatField(null=True)
    subtotal = models.FloatField(null=True)

    metadata_1 = models.CharField(max_length=64, blank=True, null=True)
    metadata_2 = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        verbose_name = _("ATHM Transaction")
        verbose_name_plural = _("ATHM Transactions")

    def __str__(self):
        return self.reference_number

    http_adapter = get_http_adapter()

    @classmethod
    def list(cls, start_date, end_date):
        response = cls.http_adapter.get_with_data(
            url=LIST_URL,
            data=dict(
                publicToken=settings.PUBLIC_TOKEN,
                privateToken=settings.PRIVATE_TOKEN,
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
        if response["refundStatus"] == COMPLETED_STATUS:
            transaction.status = cls.REFUNDED
            transaction.refunded_amount = response["refundedAmount"]
            transaction.save()

        return response

    @classmethod
    def inspect(cls, transaction):
        response = cls.http_adapter.post(
            STATUS_URL,
            data=dict(
                publicToken=settings.PUBLIC_TOKEN,
                privateToken=settings.PRIVATE_TOKEN,
                referenceNumber=transaction.reference_number,
            ),
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

    price = models.FloatField()
    tax = models.FloatField(null=True)
    metadata = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        verbose_name = _("ATHM Item")
        verbose_name_plural = _("ATHM Items")

    def __str__(self):
        return self.name
