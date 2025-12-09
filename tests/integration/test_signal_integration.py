import uuid
from decimal import Decimal

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
        """Verify testapp receives payment_cancelled signal."""
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-integration-cancelled",
            status=Payment.Status.CANCEL,
            total=Decimal("50.00"),
        )

        signals.payment_cancelled.send(sender=Payment, payment=payment)

        assert hasattr(payment, "_signal_handlers_called")
        assert "payment_cancelled" in payment._signal_handlers_called

    def test_testapp_receives_payment_expired(self):
        """Verify testapp receives payment_expired signal."""
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-integration-expired",
            status=Payment.Status.EXPIRED,
            total=Decimal("50.00"),
        )

        signals.payment_expired.send(sender=Payment, payment=payment)

        assert hasattr(payment, "_signal_handlers_called")
        assert "payment_expired" in payment._signal_handlers_called

    def test_testapp_receives_refund_sent(self):
        """Verify testapp receives refund_sent signal."""
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
