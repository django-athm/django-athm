import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from django_athm import signals
from django_athm.models import Payment, Refund

pytestmark = pytest.mark.django_db


class TestPaymentSignals:
    def test_payment_completed_signal_fires(self):
        handler = MagicMock()
        signals.payment_completed.connect(handler)

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-completed",
            status=Payment.Status.COMPLETED,
            total=Decimal("50.00"),
        )

        signals.payment_completed.send(sender=Payment, payment=payment)

        handler.assert_called_once()
        call_kwargs = handler.call_args[1]
        assert call_kwargs["sender"] == Payment
        assert call_kwargs["payment"] == payment

        signals.payment_completed.disconnect(handler)

    def test_payment_failed_signal_fires(self):
        handler = MagicMock()
        signals.payment_failed.connect(handler)

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-failed",
            status=Payment.Status.CANCEL,
            total=Decimal("50.00"),
        )

        signals.payment_failed.send(sender=Payment, payment=payment, reason="cancelled")

        handler.assert_called_once()
        call_kwargs = handler.call_args[1]
        assert call_kwargs["payment"] == payment
        assert call_kwargs["reason"] == "cancelled"

        signals.payment_failed.disconnect(handler)

    def test_payment_expired_signal_fires(self):
        handler = MagicMock()
        signals.payment_expired.connect(handler)

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-expired",
            status=Payment.Status.EXPIRED,
            total=Decimal("50.00"),
        )

        signals.payment_expired.send(sender=Payment, payment=payment)

        handler.assert_called_once()
        call_kwargs = handler.call_args[1]
        assert call_kwargs["payment"] == payment

        signals.payment_expired.disconnect(handler)

    def test_refund_completed_signal_fires(self):
        handler = MagicMock()
        signals.refund_completed.connect(handler)

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-payment",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )

        refund = Refund.objects.create(
            payment=payment,
            reference_number="test-refund",
            amount=Decimal("50.00"),
            status="COMPLETED",
            transaction_date=timezone.now(),
        )

        signals.refund_completed.send(sender=Refund, refund=refund, payment=payment)

        handler.assert_called_once()
        call_kwargs = handler.call_args[1]
        assert call_kwargs["refund"] == refund
        assert call_kwargs["payment"] == payment

        signals.refund_completed.disconnect(handler)
