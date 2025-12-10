import concurrent.futures
import hashlib
import uuid
from decimal import Decimal

import pytest
from athm import parse_webhook
from django.db import connection

from django_athm import signals
from django_athm.models import Client, Payment, Refund, WebhookEvent
from django_athm.services.webhook_processor import WebhookProcessor

pytestmark = pytest.mark.django_db


def make_completed_payload(ecommerce_id: str | None = None) -> dict:
    """Build a COMPLETED webhook payload."""
    return {
        "transactionType": "ecommerce",
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
        "date": "2024-01-15 10:30:00",
    }


def make_cancelled_payload(ecommerce_id: str | None = None) -> dict:
    """Build a CANCEL webhook payload."""
    return {
        "transactionType": "ecommerce",
        "ecommerceId": ecommerce_id or str(uuid.uuid4()),
        "status": "CANCEL",
        "total": 50.00,
        "date": "2024-01-15 10:30:00",
    }


def make_expired_payload(ecommerce_id: str | None = None) -> dict:
    """Build an EXPIRED webhook payload."""
    return {
        "transactionType": "ecommerce",
        "ecommerceId": ecommerce_id or str(uuid.uuid4()),
        "status": "EXPIRED",
        "total": 50.00,
        "date": "2024-01-15 10:30:00",
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
        "total": 25.00,
        "date": "2024-01-15 10:30:00",
    }


class TestIdempotencyKeyComputation:
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
    def test_skips_already_processed_event(self, mocker):
        event = WebhookEvent.objects.create(
            idempotency_key="test-key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=make_completed_payload(),
            remote_ip="127.0.0.1",
            processed=True,
        )
        spy = mocker.spy(WebhookProcessor, "_handle_ecommerce_completed")

        WebhookProcessor.process(event, parse_webhook(event.payload))

        spy.assert_not_called()

    def test_marks_unknown_event_as_processed(self):
        payload = {
            "transactionType": "donation",
            "status": "completed",
            "total": 0.00,
            "date": "2024-01-15 10:30:00",
        }
        event = WebhookEvent.objects.create(
            idempotency_key="unknown-key",
            event_type=WebhookEvent.Type.UNKNOWN,
            payload=payload,
            remote_ip="127.0.0.1",
            processed=False,
        )

        WebhookProcessor.process(event, parse_webhook(event.payload))

        event.refresh_from_db()
        assert event.processed is True


class TestHandleEcommerceCompleted:
    def test_creates_payment_from_webhook(self):
        ecommerce_id = str(uuid.uuid4())
        payload = make_completed_payload(ecommerce_id)
        event = WebhookEvent.objects.create(
            idempotency_key="test",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event, parse_webhook(event.payload))

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

        WebhookProcessor.process(event, parse_webhook(event.payload))

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.status == Payment.Status.COMPLETED

    def test_enriches_already_completed_payment(self):
        """Webhook data enriches already-completed payment (e.g., from authorize endpoint)."""
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
        payload["fee"] = "1.50"
        payload["netAmount"] = "98.50"
        event = WebhookEvent.objects.create(
            idempotency_key="test",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event, parse_webhook(event.payload))

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        # Webhook data enriches the payment
        assert payment.reference_number == "new-ref-number"
        assert payment.fee == Decimal("1.50")
        assert payment.net_amount == Decimal("98.50")

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

            WebhookProcessor.process(event, parse_webhook(event.payload))

            handler.assert_called_once()
            call_kwargs = handler.call_args[1]
            assert call_kwargs["sender"] == Payment
            assert call_kwargs["payment"].status == Payment.Status.COMPLETED
        finally:
            signals.payment_completed.disconnect(handler)

    @pytest.mark.django_db(transaction=True)
    def test_no_signal_when_enriching_already_completed(self, mocker):
        """Signal should not fire when enriching an already-completed payment."""
        from django_athm import signals

        handler = mocker.Mock()
        signals.payment_completed.connect(handler)

        try:
            ecommerce_id = str(uuid.uuid4())
            Payment.objects.create(
                ecommerce_id=ecommerce_id,
                status=Payment.Status.COMPLETED,
                reference_number="original-ref",
                total=Decimal("100.00"),
            )
            payload = make_completed_payload(ecommerce_id)
            event = WebhookEvent.objects.create(
                idempotency_key="enrich-test",
                event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
                payload=payload,
                remote_ip="127.0.0.1",
            )

            WebhookProcessor.process(event, parse_webhook(event.payload))

            handler.assert_not_called()
        finally:
            signals.payment_completed.disconnect(handler)

    def test_missing_ecommerce_id_marks_processed(self):
        payload = {
            "transactionType": "ecommerce",
            "status": "COMPLETED",
            "total": 100.00,
            "date": "2024-01-15 10:30:00",
        }
        event = WebhookEvent.objects.create(
            idempotency_key="missing-id",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event, parse_webhook(event.payload))

        event.refresh_from_db()
        assert event.processed is True
        assert Payment.objects.count() == 0


class TestHandleEcommerceCancelled:
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

        WebhookProcessor.process(event, parse_webhook(event.payload))

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

        WebhookProcessor.process(event, parse_webhook(event.payload))

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.status == Payment.Status.COMPLETED  # Unchanged

    @pytest.mark.django_db(transaction=True)
    def test_sends_payment_cancelled_signal(self, mocker):
        from django_athm import signals

        handler = mocker.Mock()
        signals.payment_cancelled.connect(handler)

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

            WebhookProcessor.process(event, parse_webhook(event.payload))

            handler.assert_called_once()
            call_kwargs = handler.call_args[1]
            assert call_kwargs["sender"] == Payment
            assert call_kwargs["payment"].status == Payment.Status.CANCEL
        finally:
            signals.payment_cancelled.disconnect(handler)


class TestHandleEcommerceExpired:
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

        WebhookProcessor.process(event, parse_webhook(event.payload))

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

        WebhookProcessor.process(event, parse_webhook(event.payload))

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.status == Payment.Status.COMPLETED  # Unchanged


class TestHandleRefund:
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

        WebhookProcessor.process(event, parse_webhook(event.payload))

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

        WebhookProcessor.process(event, parse_webhook(event.payload))

        assert Refund.objects.filter(reference_number="ref-dup").count() == 1

    def test_skips_refund_without_matching_payment(self):
        payload = make_refund_payload("nonexistent-ref")
        event = WebhookEvent.objects.create(
            idempotency_key="orphan-refund",
            event_type=WebhookEvent.Type.REFUND_SENT,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event, parse_webhook(event.payload))

        event.refresh_from_db()
        assert event.processed is True
        assert Refund.objects.count() == 0

    def test_missing_reference_number_marks_processed(self):
        payload = {
            "transactionType": "REFUND",
            "status": "COMPLETED",
            "total": 25.00,
            "date": "2024-01-15 10:30:00",
        }
        event = WebhookEvent.objects.create(
            idempotency_key="bad-refund",
            event_type=WebhookEvent.Type.REFUND_SENT,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event, parse_webhook(event.payload))

        event.refresh_from_db()
        assert event.processed is True


class TestClientLinking:
    def test_creates_client_from_completed_payment(self):
        ecommerce_id = str(uuid.uuid4())
        payload = make_completed_payload(ecommerce_id)
        event = WebhookEvent.objects.create(
            idempotency_key="client-test",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event, parse_webhook(event.payload))

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.client is not None
        assert payment.client.phone_number == "7871234567"
        assert payment.client.name == "Test Customer"
        assert payment.client.email == "test@example.com"

    def test_reuses_existing_client_by_phone(self):
        # Create existing client
        existing_client = Client.objects.create(
            phone_number="7871234567",
            name="Old Name",
            email="old@example.com",
        )

        ecommerce_id = str(uuid.uuid4())
        payload = make_completed_payload(ecommerce_id)
        event = WebhookEvent.objects.create(
            idempotency_key="reuse-client",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event, parse_webhook(event.payload))

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.client == existing_client
        assert Client.objects.count() == 1

        # Check that client was updated with latest info
        existing_client.refresh_from_db()
        assert existing_client.name == "Test Customer"
        assert existing_client.email == "test@example.com"

    def test_creates_client_from_refund(self):
        Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="ref-for-refund",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        payload = make_refund_payload("ref-for-refund")
        event = WebhookEvent.objects.create(
            idempotency_key="refund-client",
            event_type=WebhookEvent.Type.REFUND_SENT,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event, parse_webhook(event.payload))

        refund = Refund.objects.get(reference_number="ref-for-refund")
        assert refund.client is not None
        assert refund.client.phone_number == "7871234567"

    def test_no_client_created_without_phone(self):
        ecommerce_id = str(uuid.uuid4())
        payload = make_completed_payload(ecommerce_id)
        payload["phoneNumber"] = ""  # No phone number
        event = WebhookEvent.objects.create(
            idempotency_key="no-phone",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            payload=payload,
            remote_ip="127.0.0.1",
        )

        WebhookProcessor.process(event, parse_webhook(event.payload))

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.client is None
        assert Client.objects.count() == 0


class TestIdempotencyGuarantees:
    """Critical idempotency scenarios for webhook processing."""

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_duplicate_webhooks_create_single_event(self):
        """Verify database constraint prevents duplicate events under race conditions."""
        payload = make_completed_payload()
        results = []

        def store_webhook():
            # Force new connection per thread
            connection.close()
            try:
                _, created = WebhookProcessor.store_event(
                    payload, remote_ip="127.0.0.1"
                )
                return created
            except Exception:
                # IntegrityError expected for duplicates
                return False

        # Simulate 5 concurrent webhook deliveries
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(store_webhook) for _ in range(5)]
            results = [f.result() for f in futures]

        # Exactly one should succeed
        assert sum(results) == 1
        assert WebhookEvent.objects.count() == 1

    @pytest.mark.django_db(transaction=True)
    def test_duplicate_webhook_does_not_fire_signal_twice(self, mocker):
        """Verify signals fire only once even if webhook received multiple times."""
        handler = mocker.Mock()
        signals.payment_completed.connect(handler)

        try:
            payload = make_completed_payload()

            # First delivery
            event1, _ = WebhookProcessor.store_event(payload, remote_ip="127.0.0.1")
            WebhookProcessor.process(event1, parse_webhook(event1.payload))

            # Duplicate delivery (already processed)
            event2, _ = WebhookProcessor.store_event(payload, remote_ip="127.0.0.1")
            WebhookProcessor.process(event2, parse_webhook(event2.payload))

            # Signal should fire only once
            handler.assert_called_once()
        finally:
            signals.payment_completed.disconnect(handler)

    def test_cross_status_webhooks_create_separate_events(self):
        """Verify same payment with different statuses creates separate events."""
        ecommerce_id = str(uuid.uuid4())

        # COMPLETED webhook
        completed_payload = make_completed_payload(ecommerce_id)
        event1, created1 = WebhookProcessor.store_event(
            completed_payload, remote_ip="127.0.0.1"
        )

        # CANCEL webhook for same payment (different idempotency key)
        cancel_payload = make_cancelled_payload(ecommerce_id)
        event2, created2 = WebhookProcessor.store_event(
            cancel_payload, remote_ip="127.0.0.1"
        )

        assert created1 is True
        assert created2 is True
        assert event1.idempotency_key != event2.idempotency_key
        assert WebhookEvent.objects.count() == 2

    @pytest.mark.django_db(transaction=True)
    def test_duplicate_webhook_does_not_double_process_payment(self):
        """Verify duplicate webhook doesn't modify payment twice."""
        ecommerce_id = str(uuid.uuid4())
        payload = make_completed_payload(ecommerce_id)

        # First delivery - creates payment
        event1, _ = WebhookProcessor.store_event(payload, remote_ip="127.0.0.1")
        WebhookProcessor.process(event1, parse_webhook(event1.payload))

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        original_modified = payment.modified

        # Duplicate delivery (already processed, same event)
        event2, created = WebhookProcessor.store_event(payload, remote_ip="127.0.0.1")
        assert not created  # Same event returned
        WebhookProcessor.process(event2, parse_webhook(event2.payload))

        payment.refresh_from_db()
        # Payment should not be modified on duplicate
        assert payment.modified == original_modified


class TestRealWebhookIntegration:
    """Integration tests using real webhook payloads from production."""

    def test_processes_real_payment_completed_webhook(
        self, payment_completed_webhook_payload
    ):
        event, created = WebhookProcessor.store_event(
            payment_completed_webhook_payload, remote_ip="127.0.0.1"
        )

        assert created is True
        assert event.event_type == WebhookEvent.Type.ECOMMERCE_COMPLETED

        WebhookProcessor.process(event, parse_webhook(event.payload))

        event.refresh_from_db()
        assert event.processed is True

        payment = Payment.objects.get(
            ecommerce_id=payment_completed_webhook_payload["ecommerceId"]
        )
        assert payment.status == Payment.Status.COMPLETED
        assert (
            payment.reference_number
            == payment_completed_webhook_payload["referenceNumber"]
        )
        assert payment.total == Decimal("3.00")
        assert payment.fee == Decimal("0.07")
        assert payment.net_amount == Decimal("2.93")
        assert payment.customer_name == "Test Customer"
        assert payment.customer_email == "customer@example.com"
        assert payment.customer_phone == "7875551234"
        assert payment.metadata_1 == "Django ATHM Demo"
        assert payment.metadata_2 == "Project Support Tip"

        # Verify client was created
        assert payment.client is not None
        assert payment.client.phone_number == "7875551234"
        assert payment.client.name == "Test Customer"

    def test_processes_real_refund_webhook(self, refund_webhook_payload):
        # Create the original payment first
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number=refund_webhook_payload["referenceNumber"],
            status=Payment.Status.COMPLETED,
            total=Decimal("3.00"),
        )

        event, created = WebhookProcessor.store_event(
            refund_webhook_payload, remote_ip="127.0.0.1"
        )

        assert created is True
        assert event.event_type == WebhookEvent.Type.REFUND_SENT

        WebhookProcessor.process(event, parse_webhook(event.payload))

        event.refresh_from_db()
        assert event.processed is True

        refund = Refund.objects.get(
            reference_number=refund_webhook_payload["referenceNumber"]
        )
        assert refund.payment == payment
        assert refund.amount == Decimal("3.00")
        assert refund.status == "COMPLETED"
        assert refund.customer_name == "Test Customer"
        assert refund.customer_email == "customer@example.com"
