"""Tests for WebhookProcessor idempotency and event handling."""

import hashlib
import uuid
from decimal import Decimal

import pytest

from django_athm.models import Payment, PaymentLineItem, Refund, WebhookEvent
from django_athm.services.webhook_processor import WebhookProcessor

pytestmark = pytest.mark.django_db


def make_completed_payload(ecommerce_id: str | None = None) -> dict:
    """Build a COMPLETED webhook payload."""
    return {
        "ecommerceId": ecommerce_id or str(uuid.uuid4()),
        "status": "COMPLETED",
        "referenceNumber": f"ref-{uuid.uuid4().hex[:8]}",
        "dailyTransactionId": "1234",
        "name": "Test Customer",
        "phoneNumber": "7871234567",
        "email": "test@example.com",
        "message": "",
        "total": 100.00,
        "tax": 5.00,
        "subTotal": 95.00,
        "fee": 2.50,
        "netAmount": 97.50,
        "totalRefundedAmount": 0.00,
        "metadata1": "meta1",
        "metadata2": "meta2",
        "items": [],
    }


def make_cancelled_payload(ecommerce_id: str | None = None) -> dict:
    """Build a CANCEL webhook payload."""
    return {
        "ecommerceId": ecommerce_id or str(uuid.uuid4()),
        "status": "CANCEL",
        "total": 50.00,
    }


def make_expired_payload(ecommerce_id: str | None = None) -> dict:
    """Build an EXPIRED webhook payload."""
    return {
        "ecommerceId": ecommerce_id or str(uuid.uuid4()),
        "status": "EXPIRED",
        "total": 50.00,
    }


def make_refund_payload(reference_number: str) -> dict:
    """Build a REFUND webhook payload."""
    return {
        "transactionType": "REFUND",
        "status": "COMPLETED",
        "referenceNumber": reference_number,
        "dailyTransactionId": "5678",
        "name": "Test Customer",
        "phoneNumber": "7871234567",
        "email": "test@example.com",
        "amount": 25.00,
        "date": "2024-01-15 10:30:00",
    }


class TestIdempotencyKeyComputation:
    """Test that idempotency keys are computed correctly and deterministically."""

    def test_ecommerce_completed_key_uses_id_and_status(self):
        payload = {
            "ecommerceId": "abc-123",
            "status": "COMPLETED",
        }
        key = WebhookProcessor._compute_idempotency_key(payload)

        expected = hashlib.sha256(b"abc-123:COMPLETED").hexdigest()[:32]
        assert key == expected

    def test_ecommerce_cancelled_key_uses_id_and_status(self):
        payload = {
            "ecommerceId": "abc-123",
            "status": "CANCEL",
        }
        key = WebhookProcessor._compute_idempotency_key(payload)

        expected = hashlib.sha256(b"abc-123:CANCEL").hexdigest()[:32]
        assert key == expected

    def test_refund_key_uses_refund_prefix_and_reference(self):
        payload = {
            "transactionType": "REFUND",
            "referenceNumber": "ref-xyz-789",
        }
        key = WebhookProcessor._compute_idempotency_key(payload)

        expected = hashlib.sha256(b"refund:ref-xyz-789").hexdigest()[:32]
        assert key == expected

    def test_payment_key_uses_type_and_reference(self):
        payload = {
            "transactionType": "PAYMENT",
            "referenceNumber": "pay-123",
        }
        key = WebhookProcessor._compute_idempotency_key(payload)

        expected = hashlib.sha256(b"PAYMENT:pay-123").hexdigest()[:32]
        assert key == expected

    def test_key_is_deterministic(self):
        payload = make_completed_payload()
        key1 = WebhookProcessor._compute_idempotency_key(payload)
        key2 = WebhookProcessor._compute_idempotency_key(payload)

        assert key1 == key2


class TestEventTypeDetection:
    """Test that event types are correctly detected from payloads."""

    def test_ecommerce_completed(self):
        payload = {"ecommerceId": "123", "status": "COMPLETED"}
        assert (
            WebhookProcessor._determine_event_type(payload)
            == WebhookEvent.Type.ECOMMERCE_COMPLETED
        )

    def test_ecommerce_cancelled(self):
        payload = {"ecommerceId": "123", "status": "CANCEL"}
        assert (
            WebhookProcessor._determine_event_type(payload)
            == WebhookEvent.Type.ECOMMERCE_CANCELLED
        )

    def test_ecommerce_expired(self):
        payload = {"ecommerceId": "123", "status": "EXPIRED"}
        assert (
            WebhookProcessor._determine_event_type(payload)
            == WebhookEvent.Type.ECOMMERCE_EXPIRED
        )

    def test_refund(self):
        payload = {"transactionType": "REFUND", "referenceNumber": "ref-123"}
        assert (
            WebhookProcessor._determine_event_type(payload)
            == WebhookEvent.Type.REFUND_SENT
        )

    def test_payment(self):
        payload = {"transactionType": "PAYMENT", "referenceNumber": "pay-123"}
        assert (
            WebhookProcessor._determine_event_type(payload)
            == WebhookEvent.Type.PAYMENT_RECEIVED
        )

    def test_donation(self):
        payload = {"transactionType": "DONATION", "referenceNumber": "don-123"}
        assert (
            WebhookProcessor._determine_event_type(payload)
            == WebhookEvent.Type.DONATION_RECEIVED
        )

    def test_simulated(self):
        payload = {"transactionType": "SIMULATED"}
        assert (
            WebhookProcessor._determine_event_type(payload)
            == WebhookEvent.Type.SIMULATED
        )

    def test_unknown_returns_unknown(self):
        payload = {"foo": "bar"}
        assert (
            WebhookProcessor._determine_event_type(payload) == WebhookEvent.Type.UNKNOWN
        )

    def test_ecommerce_with_unknown_status_returns_unknown(self):
        payload = {"ecommerceId": "123", "status": "PENDING"}
        assert (
            WebhookProcessor._determine_event_type(payload) == WebhookEvent.Type.UNKNOWN
        )


class TestStoreEvent:
    """Test webhook event storage and duplicate detection."""

    def test_creates_new_event(self):
        payload = make_completed_payload()

        event, created = WebhookProcessor.store_event(payload, remote_ip="127.0.0.1")

        assert created is True
        assert event.event_type == WebhookEvent.Type.ECOMMERCE_COMPLETED
        assert event.remote_ip == "127.0.0.1"
        assert event.processed is False
        assert WebhookEvent.objects.count() == 1

    @pytest.mark.django_db(transaction=True)
    def test_duplicate_returns_existing_event(self):
        payload = make_completed_payload()

        event1, created1 = WebhookProcessor.store_event(payload, remote_ip="127.0.0.1")
        event2, created2 = WebhookProcessor.store_event(payload, remote_ip="127.0.0.1")

        assert created1 is True
        assert created2 is False
        assert event1.id == event2.id
        assert WebhookEvent.objects.count() == 1

    def test_different_payloads_create_different_events(self):
        payload1 = make_completed_payload()
        payload2 = make_completed_payload()  # Different UUID

        _, created1 = WebhookProcessor.store_event(payload1, remote_ip="127.0.0.1")
        _, created2 = WebhookProcessor.store_event(payload2, remote_ip="127.0.0.1")

        assert created1 is True
        assert created2 is True
        assert WebhookEvent.objects.count() == 2


class TestProcessEvent:
    """Test event processing and handler dispatch."""

    def test_skips_already_processed_event(self, mocker):
        event = WebhookEvent.objects.create(
            idempotency_key="test-key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=make_completed_payload(),
            remote_ip="127.0.0.1",
            processed=True,
        )
        spy = mocker.spy(WebhookProcessor, "_handle_ecommerce_completed")

        WebhookProcessor.process(event)

        spy.assert_not_called()

    def test_marks_unknown_event_as_processed(self):
        event = WebhookEvent.objects.create(
            idempotency_key="unknown-key",
            event_type=WebhookEvent.Type.UNKNOWN,
            payload={"foo": "bar"},
            remote_ip="127.0.0.1",
            processed=False,
        )

        WebhookProcessor.process(event)

        event.refresh_from_db()
        assert event.processed is True


class TestHandleEcommerceCompleted:
    """Test COMPLETED webhook handler."""

    def test_creates_payment_from_webhook(self):
        ecommerce_id = str(uuid.uuid4())
        payload = make_completed_payload(ecommerce_id)
        event = WebhookEvent.objects.create(
            idempotency_key="test",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.status == Payment.Status.COMPLETED
        assert payment.reference_number == payload["referenceNumber"]
        assert payment.fee == Decimal("2.50")
        assert payment.net_amount == Decimal("97.50")
        assert payment.customer_name == "Test Customer"
        assert payment.customer_email == "test@example.com"

    def test_updates_existing_payment_to_completed(self):
        ecommerce_id = str(uuid.uuid4())
        Payment.objects.create(
            ecommerce_id=ecommerce_id,
            status=Payment.Status.CONFIRM,
            total=Decimal("100.00"),
        )
        payload = make_completed_payload(ecommerce_id)
        event = WebhookEvent.objects.create(
            idempotency_key="test",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.status == Payment.Status.COMPLETED

    def test_skips_already_completed_payment(self):
        ecommerce_id = str(uuid.uuid4())
        original_ref = "original-ref-number"
        Payment.objects.create(
            ecommerce_id=ecommerce_id,
            status=Payment.Status.COMPLETED,
            reference_number=original_ref,
            total=Decimal("100.00"),
        )
        payload = make_completed_payload(ecommerce_id)
        payload["referenceNumber"] = "new-ref-number"
        event = WebhookEvent.objects.create(
            idempotency_key="test",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.reference_number == original_ref  # Unchanged

    @pytest.mark.django_db(transaction=True)
    def test_sends_payment_completed_signal(self, mocker):
        from django_athm import signals

        handler = mocker.Mock()
        signals.payment_completed.connect(handler)

        try:
            payload = make_completed_payload()
            event = WebhookEvent.objects.create(
                idempotency_key="signal-test",
                event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
                payload=payload,
                remote_ip="127.0.0.1",
            )

            WebhookProcessor.process(event)

            handler.assert_called_once()
            call_kwargs = handler.call_args[1]
            assert call_kwargs["sender"] == Payment
            assert call_kwargs["payment"].status == Payment.Status.COMPLETED
        finally:
            signals.payment_completed.disconnect(handler)

    def test_missing_ecommerce_id_marks_processed(self):
        payload = {"status": "COMPLETED"}  # Missing ecommerceId
        event = WebhookEvent.objects.create(
            idempotency_key="missing-id",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        event.refresh_from_db()
        assert event.processed is True
        assert Payment.objects.count() == 0


class TestHandleEcommerceCancelled:
    """Test CANCEL webhook handler."""

    def test_updates_payment_to_cancelled(self):
        ecommerce_id = str(uuid.uuid4())
        Payment.objects.create(
            ecommerce_id=ecommerce_id,
            status=Payment.Status.OPEN,
            total=Decimal("50.00"),
        )
        payload = make_cancelled_payload(ecommerce_id)
        event = WebhookEvent.objects.create(
            idempotency_key="cancel-test",
            event_type=WebhookEvent.Type.ECOMMERCE_CANCELLED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.status == Payment.Status.CANCEL

    def test_skips_completed_payment(self):
        ecommerce_id = str(uuid.uuid4())
        Payment.objects.create(
            ecommerce_id=ecommerce_id,
            status=Payment.Status.COMPLETED,
            total=Decimal("50.00"),
        )
        payload = make_cancelled_payload(ecommerce_id)
        event = WebhookEvent.objects.create(
            idempotency_key="skip-cancel",
            event_type=WebhookEvent.Type.ECOMMERCE_CANCELLED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.status == Payment.Status.COMPLETED  # Unchanged

    @pytest.mark.django_db(transaction=True)
    def test_sends_payment_failed_signal(self, mocker):
        from django_athm import signals

        handler = mocker.Mock()
        signals.payment_failed.connect(handler)

        try:
            ecommerce_id = str(uuid.uuid4())
            Payment.objects.create(
                ecommerce_id=ecommerce_id,
                status=Payment.Status.OPEN,
                total=Decimal("50.00"),
            )
            payload = make_cancelled_payload(ecommerce_id)
            event = WebhookEvent.objects.create(
                idempotency_key="signal-cancel",
                event_type=WebhookEvent.Type.ECOMMERCE_CANCELLED,
                payload=payload,
                remote_ip="127.0.0.1",
            )

            WebhookProcessor.process(event)

            handler.assert_called_once()
            call_kwargs = handler.call_args[1]
            assert call_kwargs["reason"] == "cancelled"
        finally:
            signals.payment_failed.disconnect(handler)


class TestHandleEcommerceExpired:
    """Test EXPIRED webhook handler."""

    def test_updates_payment_to_expired(self):
        ecommerce_id = str(uuid.uuid4())
        Payment.objects.create(
            ecommerce_id=ecommerce_id,
            status=Payment.Status.OPEN,
            total=Decimal("50.00"),
        )
        payload = make_expired_payload(ecommerce_id)
        event = WebhookEvent.objects.create(
            idempotency_key="expired-test",
            event_type=WebhookEvent.Type.ECOMMERCE_EXPIRED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.status == Payment.Status.EXPIRED

    def test_skips_completed_payment(self):
        ecommerce_id = str(uuid.uuid4())
        Payment.objects.create(
            ecommerce_id=ecommerce_id,
            status=Payment.Status.COMPLETED,
            total=Decimal("50.00"),
        )
        payload = make_expired_payload(ecommerce_id)
        event = WebhookEvent.objects.create(
            idempotency_key="skip-expired",
            event_type=WebhookEvent.Type.ECOMMERCE_EXPIRED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.status == Payment.Status.COMPLETED  # Unchanged


class TestHandleRefund:
    """Test REFUND webhook handler."""

    def test_creates_refund_linked_to_payment(self):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="ref-for-refund",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        payload = make_refund_payload("ref-for-refund")
        event = WebhookEvent.objects.create(
            idempotency_key="refund-test",
            event_type=WebhookEvent.Type.REFUND_SENT,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        refund = Refund.objects.get(reference_number="ref-for-refund")
        assert refund.payment == payment
        assert refund.amount == Decimal("25.00")

    def test_skips_duplicate_refund(self):
        from django.utils import timezone

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="ref-dup",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        Refund.objects.create(
            payment=payment,
            reference_number="ref-dup",
            amount=Decimal("25.00"),
            status="COMPLETED",
            transaction_date=timezone.now(),
        )
        payload = make_refund_payload("ref-dup")
        event = WebhookEvent.objects.create(
            idempotency_key="dup-refund",
            event_type=WebhookEvent.Type.REFUND_SENT,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        assert Refund.objects.filter(reference_number="ref-dup").count() == 1

    def test_skips_refund_without_matching_payment(self):
        payload = make_refund_payload("nonexistent-ref")
        event = WebhookEvent.objects.create(
            idempotency_key="orphan-refund",
            event_type=WebhookEvent.Type.REFUND_SENT,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        event.refresh_from_db()
        assert event.processed is True
        assert Refund.objects.count() == 0

    def test_missing_reference_number_marks_processed(self):
        payload = {"transactionType": "REFUND"}  # Missing referenceNumber
        event = WebhookEvent.objects.create(
            idempotency_key="bad-refund",
            event_type=WebhookEvent.Type.REFUND_SENT,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        event.refresh_from_db()
        assert event.processed is True


class TestSyncItems:
    """Test line item syncing from webhooks."""

    def test_creates_line_items_from_payload(self):
        ecommerce_id = str(uuid.uuid4())
        payload = make_completed_payload(ecommerce_id)
        payload["items"] = [
            {"name": "Item 1", "price": 50.00, "quantity": 2, "tax": 5.00},
            {"name": "Item 2", "price": 45.00, "quantity": 1, "tax": 0.00},
        ]
        event = WebhookEvent.objects.create(
            idempotency_key="items-test",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.items.count() == 2
        item1 = payment.items.get(name="Item 1")
        assert item1.price == Decimal("50.00")
        assert item1.quantity == 2

    def test_skips_sync_if_items_already_exist(self):
        ecommerce_id = str(uuid.uuid4())
        payment = Payment.objects.create(
            ecommerce_id=ecommerce_id,
            status=Payment.Status.CONFIRM,
            total=Decimal("100.00"),
        )
        PaymentLineItem.objects.create(
            transaction=payment, name="Existing Item", price=Decimal("100.00")
        )
        payload = make_completed_payload(ecommerce_id)
        payload["items"] = [{"name": "New Item", "price": 50.00}]
        event = WebhookEvent.objects.create(
            idempotency_key="skip-items",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event)

        payment.refresh_from_db()
        assert payment.items.count() == 1
        assert payment.items.first().name == "Existing Item"


class TestParseDatetime:
    """Test datetime parsing from various ATH Movil formats."""

    def test_parses_string_format(self):
        dt = WebhookProcessor._parse_datetime("2024-01-15 10:30:00")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_parses_millisecond_timestamp(self):
        # 1705315800000 = 2024-01-15 10:30:00 UTC
        dt = WebhookProcessor._parse_datetime(1705315800000)
        assert dt is not None

    def test_parses_second_timestamp(self):
        dt = WebhookProcessor._parse_datetime(1705315800)
        assert dt is not None

    def test_returns_none_for_invalid(self):
        assert WebhookProcessor._parse_datetime("invalid") is None
        assert WebhookProcessor._parse_datetime(None) is None
        assert WebhookProcessor._parse_datetime("") is None


class TestShouldSkipUpdate:
    """Test terminal state checking logic."""

    def test_completed_payment_skips_completed_check(self):
        payment = Payment(status=Payment.Status.COMPLETED)
        assert WebhookProcessor._should_skip_update(payment, check_completed=True)

    def test_open_payment_does_not_skip_completed_check(self):
        payment = Payment(status=Payment.Status.OPEN)
        assert not WebhookProcessor._should_skip_update(payment, check_completed=True)

    def test_completed_payment_skips_terminal_check(self):
        payment = Payment(status=Payment.Status.COMPLETED)
        assert WebhookProcessor._should_skip_update(payment, check_completed=False)

    def test_cancelled_payment_skips_terminal_check(self):
        payment = Payment(status=Payment.Status.CANCEL)
        assert WebhookProcessor._should_skip_update(payment, check_completed=False)

    def test_expired_payment_skips_terminal_check(self):
        payment = Payment(status=Payment.Status.EXPIRED)
        assert WebhookProcessor._should_skip_update(payment, check_completed=False)

    def test_open_payment_does_not_skip_terminal_check(self):
        payment = Payment(status=Payment.Status.OPEN)
        assert not WebhookProcessor._should_skip_update(payment, check_completed=False)

    def test_confirm_payment_does_not_skip_terminal_check(self):
        payment = Payment(status=Payment.Status.CONFIRM)
        assert not WebhookProcessor._should_skip_update(payment, check_completed=False)
