import uuid
from decimal import Decimal

import pytest

from django_athm import models

pytestmark = pytest.mark.django_db


class TestPayment:
    def test_can_save_payment(self):
        models.Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-reference-number",
            status=models.Payment.Status.OPEN,
            total=Decimal("25.50"),
            tax=Decimal("1.75"),
            subtotal=Decimal("23.75"),
            metadata_1="Testing Metadata 1",
        )

        stored_payments = models.Payment.objects.all()
        assert len(stored_payments) == 1
        assert stored_payments[0].reference_number == "test-reference-number"

    def test_str_representation_with_reference_number(self):
        payment = models.Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-reference-number",
            status=models.Payment.Status.COMPLETED,
            total=Decimal("25.50"),
        )
        assert str(payment) == "test-reference-number"

    def test_str_representation_without_reference_number(self):
        ecommerce_id = uuid.uuid4()
        payment = models.Payment(
            ecommerce_id=ecommerce_id,
            reference_number="",
            status=models.Payment.Status.OPEN,
            total=Decimal("25.50"),
        )
        assert str(payment) == str(ecommerce_id)

    def test_is_successful_property(self):
        completed_payment = models.Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="completed",
            status=models.Payment.Status.COMPLETED,
            total=Decimal("10.00"),
        )
        open_payment = models.Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="open",
            status=models.Payment.Status.OPEN,
            total=Decimal("10.00"),
        )

        assert completed_payment.is_successful is True
        assert open_payment.is_successful is False

    def test_is_refundable_property(self):
        # Completed with net_amount > total_refunded_amount
        refundable = models.Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="refundable",
            status=models.Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            total_refunded_amount=Decimal("0.00"),
        )
        assert refundable.is_refundable is True

        # Completed but fully refunded
        fully_refunded = models.Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="fully-refunded",
            status=models.Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            total_refunded_amount=Decimal("100.00"),
        )
        assert fully_refunded.is_refundable is False

        # Not completed
        not_completed = models.Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="not-completed",
            status=models.Payment.Status.OPEN,
            total=Decimal("100.00"),
        )
        assert not_completed.is_refundable is False

    def test_refundable_amount_property(self):
        payment = models.Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="test",
            status=models.Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            total_refunded_amount=Decimal("25.00"),
        )
        assert payment.refundable_amount == Decimal("75.00")

        # Not refundable should return 0
        not_refundable = models.Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="not-refundable",
            status=models.Payment.Status.OPEN,
            total=Decimal("100.00"),
        )
        assert not_refundable.refundable_amount == Decimal("0.00")

    def test_status_choices(self):
        assert models.Payment.Status.OPEN == "OPEN"
        assert models.Payment.Status.CONFIRM == "CONFIRM"
        assert models.Payment.Status.COMPLETED == "COMPLETED"
        assert models.Payment.Status.CANCEL == "CANCEL"
        assert models.Payment.Status.EXPIRED == "EXPIRED"


class TestPaymentLineItem:
    def test_can_create_line_item(self):
        payment = models.Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test",
            status=models.Payment.Status.COMPLETED,
            total=Decimal("50.00"),
        )

        item = models.PaymentLineItem.objects.create(
            transaction=payment,
            name="Test Item",
            description="A test item",
            quantity=2,
            price=Decimal("25.00"),
            tax=Decimal("2.50"),
        )

        assert item.name == "Test Item"
        assert item.transaction == payment
        assert str(item) == "Test Item"

    def test_line_item_relationship(self):
        payment = models.Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test",
            status=models.Payment.Status.COMPLETED,
            total=Decimal("50.00"),
        )

        models.PaymentLineItem.objects.create(
            transaction=payment,
            name="Item 1",
            price=Decimal("25.00"),
        )
        models.PaymentLineItem.objects.create(
            transaction=payment,
            name="Item 2",
            price=Decimal("25.00"),
        )

        assert payment.items.count() == 2


class TestRefund:
    def test_can_create_refund(self):
        from django.utils import timezone

        payment = models.Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="payment-ref",
            status=models.Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )

        refund = models.Refund.objects.create(
            payment=payment,
            reference_number="refund-ref",
            amount=Decimal("50.00"),
            status="COMPLETED",
            transaction_date=timezone.now(),
        )

        assert refund.payment == payment
        assert refund.amount == Decimal("50.00")
        assert payment.refunds.count() == 1


class TestWebhookEvent:
    def test_can_create_webhook_event(self):
        event = models.WebhookEvent.objects.create(
            idempotency_key="test-key-123",
            event_type=models.WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={"test": "data"},
        )

        assert event.idempotency_key == "test-key-123"
        assert event.processed is False
        assert "ecommerce_completed" in str(event)

    def test_webhook_event_types(self):
        assert models.WebhookEvent.Type.ECOMMERCE_COMPLETED == "ecommerce_completed"
        assert models.WebhookEvent.Type.ECOMMERCE_CANCELLED == "ecommerce_cancelled"
        assert models.WebhookEvent.Type.ECOMMERCE_EXPIRED == "ecommerce_expired"
        assert models.WebhookEvent.Type.REFUND_SENT == "refund"
        assert models.WebhookEvent.Type.PAYMENT_RECEIVED == "payment"

    def test_str_representation(self):
        event = models.WebhookEvent(
            idempotency_key="test",
            event_type=models.WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            processed=False,
        )
        assert "pending" in str(event)

        event.processed = True
        assert "processed" in str(event)
