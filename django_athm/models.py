import uuid

import phonenumbers
from django.core.exceptions import ValidationError
from django.db import models
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

    # NOTE: different from the API's status values
    class Status(models.TextChoices):
        PROCESSING = "processing", _("processing")
        COMPLETED = "completed", _("completed")
        REFUNDED = "refunded", _("refunded")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(unique=True, max_length=64)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PROCESSING,
    )

    date = models.DateTimeField(blank=True)

    total = models.FloatField()
    tax = models.FloatField(null=True)
    refunded_amount = models.FloatField(null=True)
    subtotal = models.FloatField(null=True)

    fee = models.FloatField(null=True)

    message = models.CharField(max_length=512, blank=True, null=True)
    metadata_1 = models.CharField(max_length=64, blank=True, null=True)
    metadata_2 = models.CharField(max_length=64, blank=True, null=True)

    client = models.ForeignKey(
        ATHM_Client,
        null=True,
        on_delete=models.CASCADE,
        related_name="transactions",
        related_query_name="transaction",
    )

    class Meta:
        verbose_name = _("ATH Móvil Transaction")
        verbose_name_plural = _("ATH Móvil Transactions")

    def __str__(self):
        return self.reference_number

    http_adapter = get_http_adapter()

    @property
    def net_amount(self):
        if not self.fee:
            return self.total

        return float(self.total - self.fee)

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
        ).json()

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

        return response.json()


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
        verbose_name = _("ATH Móvil Item")
        verbose_name_plural = _("ATH Móvil Items")

    def __str__(self):
        return self.name
