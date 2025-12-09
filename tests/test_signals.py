import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from django_athm import signals
from django_athm.models import Payment, Refund

pytestmark = pytest.mark.django_db


class TestSignalIntegration:
    """Test that signals are received by a real Django app (testapp)."""

    def test_testapp_receives_payment_completed(self):
        """Verify testapp signal handlers are auto-loaded via AppConfig.ready()."""
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-integration",
            status=Payment.Status.COMPLETED,
            total=Decimal("50.00"),
        )

        # Fire signal
        signals.payment_completed.send(sender=Payment, payment=payment)

        # Verify testapp handler was called
        assert hasattr(payment, "_signal_handlers_called")
        assert "payment_completed" in payment._signal_handlers_called

    def test_testapp_receives_payment_cancelled(self):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-integration-cancelled",
            status=Payment.Status.CANCEL,
            total=Decimal("50.00"),
        )

        signals.payment_cancelled.send(sender=Payment, payment=payment)

        assert hasattr(payment, "_signal_handlers_called")
        assert "payment_cancelled" in payment._signal_handlers_called

    def test_testapp_receives_refund_sent(self):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-integration-refund",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )

        refund = Refund.objects.create(
            payment=payment,
            reference_number="test-refund-integration",
            amount=Decimal("50.00"),
            status="COMPLETED",
            transaction_date=timezone.now(),
        )

        signals.refund_sent.send(sender=Refund, refund=refund, payment=payment)

        assert hasattr(refund, "_signal_handlers_called")
        assert "refund_sent" in refund._signal_handlers_called


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

    def test_payment_cancelled_signal_fires(self):
        handler = MagicMock()
        signals.payment_cancelled.connect(handler)

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-cancelled",
            status=Payment.Status.CANCEL,
            total=Decimal("50.00"),
        )

        signals.payment_cancelled.send(sender=Payment, payment=payment)

        handler.assert_called_once()
        call_kwargs = handler.call_args[1]
        assert call_kwargs["payment"] == payment

        signals.payment_cancelled.disconnect(handler)

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

    def test_refund_sent_signal_fires(self):
        handler = MagicMock()
        signals.refund_sent.connect(handler)

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

        signals.refund_sent.send(sender=Refund, refund=refund, payment=payment)

        handler.assert_called_once()
        call_kwargs = handler.call_args[1]
        assert call_kwargs["refund"] == refund
        assert call_kwargs["payment"] == payment

        signals.refund_sent.disconnect(handler)
