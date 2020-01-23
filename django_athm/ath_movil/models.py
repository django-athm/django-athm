import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class ATH_Transaction(models.Model):
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

    total = models.FloatField()
    tax = models.FloatField(null=True)
    refunded_amount = models.FloatField(null=True)
    subtotal = models.FloatField(null=True)

    metadata_1 = models.CharField(max_length=64, null=True)
    metadata_2 = models.CharField(max_length=64, null=True)

    class Meta:
        verbose_name = _("ATH transaction")
        verbose_name_plural = _("ATH transactions")

    def __str__(self):
        return self.reference_number

    @property
    def api_url():
        pass

    @classmethod
    def refund(cls):
        pass

    @classmethod
    def inspect(cls):
        pass


class ATH_Item(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(ATH_Transaction, on_delete=models.CASCADE)

    name = models.CharField(max_length=32)
    description = models.CharField(max_length=128)
    quantity = models.PositiveSmallIntegerField(default=1)

    price = models.FloatField()
    tax = models.FloatField(null=True)
    metadata = models.CharField(max_length=64, null=True)

    class Meta:
        verbose_name = _("ATH item")
        verbose_name_plural = _("ATH items")

    def __str__(self):
        return self.name
