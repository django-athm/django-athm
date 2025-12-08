"""Tests for PaymentService API interactions and state management."""

import uuid
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.utils import timezone

from django_athm.models import Payment
from django_athm.services.payment_service import PaymentService

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_client(mocker):
    """Mock the ATH Móvil client."""
    client = Mock()
    mocker.patch.object(PaymentService, "get_client", return_value=client)
    return client


class TestInitiate:
    """Test payment initiation."""

    def test_creates_payment_and_returns_auth_token(self, mock_client):
        ecommerce_id = str(uuid.uuid4())
        auth_token = "test-auth-token-123"

        mock_client.create_payment.return_value = Mock(
            data=Mock(ecommerce_id=ecommerce_id, auth_token=auth_token)
        )

        payment, returned_token = PaymentService.initiate(
            total=Decimal("100.00"),
            phone_number="7871234567",
            subtotal=Decimal("95.00"),
            tax=Decimal("5.00"),
            metadata_1="meta1",
            metadata_2="meta2",
        )

        assert payment.ecommerce_id == uuid.UUID(ecommerce_id)
        assert payment.status == Payment.Status.OPEN
        assert payment.total == Decimal("100.00")
        assert payment.subtotal == Decimal("95.00")
        assert payment.tax == Decimal("5.00")
        assert payment.metadata_1 == "meta1"
        assert returned_token == auth_token

        mock_client.create_payment.assert_called_once()

    def test_creates_line_items(self, mock_client):
        ecommerce_id = str(uuid.uuid4())

        mock_client.create_payment.return_value = Mock(
            data=Mock(ecommerce_id=ecommerce_id, auth_token="token")
        )

        items = [
            {"name": "Item 1", "price": "50.00", "quantity": 2, "tax": "5.00"},
            {"name": "Item 2", "price": "45.00", "description": "Test item"},
        ]

        payment, _ = PaymentService.initiate(
            total=Decimal("100.00"),
            phone_number="7871234567",
            items=items,
        )

        assert payment.items.count() == 2
        item1 = payment.items.get(name="Item 1")
        assert item1.price == Decimal("50.00")
        assert item1.quantity == 2

    def test_sends_payment_created_signal(self, mock_client, mocker):
        from django_athm import signals

        handler = mocker.Mock()
        signals.payment_created.connect(handler)

        try:
            mock_client.create_payment.return_value = Mock(
                data=Mock(ecommerce_id=str(uuid.uuid4()), auth_token="token")
            )

            payment, _ = PaymentService.initiate(
                total=Decimal("50.00"),
                phone_number="7871234567",
            )

            handler.assert_called_once()
            call_kwargs = handler.call_args[1]
            assert call_kwargs["sender"] == Payment
            assert call_kwargs["payment"] == payment
        finally:
            signals.payment_created.disconnect(handler)


class TestFindStatus:
    """Test status polling."""

    def test_returns_remote_status(self, mock_client):
        mock_client.find_payment.return_value = Mock(
            data=Mock(ecommerce_status="CONFIRM")
        )

        status = PaymentService.find_status(uuid.uuid4())

        assert status == "CONFIRM"

    def test_returns_open_when_data_is_none(self, mock_client):
        mock_client.find_payment.return_value = Mock(data=None)

        status = PaymentService.find_status(uuid.uuid4())

        assert status == Payment.Status.OPEN


class TestAuthorize:
    """Test payment authorization."""

    def test_returns_reference_number(self, mock_client):
        mock_client.authorize_payment.return_value = Mock(
            data=Mock(reference_number="ref-12345")
        )

        ref = PaymentService.authorize(uuid.uuid4(), "auth-token")

        assert ref == "ref-12345"

    def test_returns_empty_string_when_data_is_none(self, mock_client):
        mock_client.authorize_payment.return_value = Mock(data=None)

        ref = PaymentService.authorize(uuid.uuid4(), "auth-token")

        assert ref == ""


class TestCancel:
    """Test payment cancellation."""

    def test_updates_payment_status_to_cancel(self, mock_client):
        ecommerce_id = uuid.uuid4()
        payment = Payment.objects.create(
            ecommerce_id=ecommerce_id,
            status=Payment.Status.OPEN,
            total=Decimal("50.00"),
        )

        PaymentService.cancel(ecommerce_id)

        payment.refresh_from_db()
        assert payment.status == Payment.Status.CANCEL
        mock_client.cancel_payment.assert_called_once()

    def test_does_not_overwrite_completed_payment(self, mock_client):
        ecommerce_id = uuid.uuid4()
        Payment.objects.create(
            ecommerce_id=ecommerce_id,
            status=Payment.Status.COMPLETED,
            total=Decimal("50.00"),
        )

        PaymentService.cancel(ecommerce_id)

        payment = Payment.objects.get(ecommerce_id=ecommerce_id)
        assert payment.status == Payment.Status.COMPLETED

    def test_handles_missing_payment(self, mock_client):
        # Should not raise even if payment doesn't exist locally
        PaymentService.cancel(uuid.uuid4())
        mock_client.cancel_payment.assert_called_once()


class TestRefund:
    """Test refund processing."""

    def test_creates_refund_record(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="pay-ref-123",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            total_refunded_amount=Decimal("0.00"),
        )

        refund_data = Mock()
        refund_data.reference_number = "refund-ref-456"
        refund_data.daily_transaction_id = "789"
        refund_data.name = "Test User"
        refund_data.phone_number = "7871234567"
        refund_data.email = "test@example.com"
        refund_data.date = timezone.now()

        mock_client.refund_payment.return_value = Mock(data=Mock(refund=refund_data))

        refund = PaymentService.refund(payment, amount=Decimal("25.00"))

        assert refund.payment == payment
        assert refund.amount == Decimal("25.00")
        assert refund.reference_number == "refund-ref-456"

        payment.refresh_from_db()
        assert payment.total_refunded_amount == Decimal("25.00")

    def test_refunds_full_amount_when_none_specified(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="pay-ref",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            total_refunded_amount=Decimal("0.00"),
        )

        refund_data = Mock()
        refund_data.reference_number = "ref"
        refund_data.daily_transaction_id = ""
        refund_data.name = ""
        refund_data.phone_number = ""
        refund_data.email = ""
        refund_data.date = timezone.now()

        mock_client.refund_payment.return_value = Mock(data=Mock(refund=refund_data))

        refund = PaymentService.refund(payment)

        assert refund.amount == Decimal("100.00")

    def test_validates_payment_is_refundable(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            status=Payment.Status.OPEN,  # Not refundable
            total=Decimal("100.00"),
        )

        with pytest.raises(ValueError, match="not refundable"):
            PaymentService.refund(payment)

    def test_validates_amount_not_exceeding_refundable(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="ref",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            total_refunded_amount=Decimal("75.00"),  # Only $25 refundable
        )

        with pytest.raises(ValueError, match="exceeds"):
            PaymentService.refund(payment, amount=Decimal("50.00"))

    def test_validates_amount_is_positive(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="ref",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            total_refunded_amount=Decimal("0.00"),
        )

        with pytest.raises(ValueError, match="positive"):
            PaymentService.refund(payment, amount=Decimal("0.00"))

    def test_validates_payment_has_reference_number(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="",  # Missing
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            total_refunded_amount=Decimal("0.00"),
        )

        with pytest.raises(ValueError, match="no reference number"):
            PaymentService.refund(payment)

    def test_truncates_message_to_50_chars(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="ref",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            total_refunded_amount=Decimal("0.00"),
        )

        refund_data = Mock()
        refund_data.reference_number = "ref"
        refund_data.daily_transaction_id = ""
        refund_data.name = ""
        refund_data.phone_number = ""
        refund_data.email = ""
        refund_data.date = timezone.now()

        mock_client.refund_payment.return_value = Mock(data=Mock(refund=refund_data))

        long_message = "x" * 100
        PaymentService.refund(payment, message=long_message)

        call_args = mock_client.refund_payment.call_args
        assert len(call_args.kwargs["message"]) == 50


class TestSyncStatus:
    """Test status synchronization with remote."""

    def test_updates_open_to_confirm(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            status=Payment.Status.OPEN,
            total=Decimal("50.00"),
        )

        mock_client.find_payment.return_value = Mock(
            data=Mock(ecommerce_status="CONFIRM")
        )

        result = PaymentService.sync_status(payment)

        payment.refresh_from_db()
        assert payment.status == Payment.Status.CONFIRM
        assert result == Payment.Status.CONFIRM

    def test_updates_to_expired(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            status=Payment.Status.OPEN,
            total=Decimal("50.00"),
        )

        mock_client.find_payment.return_value = Mock(
            data=Mock(ecommerce_status="EXPIRED")
        )

        PaymentService.sync_status(payment)

        payment.refresh_from_db()
        assert payment.status == Payment.Status.EXPIRED

    def test_updates_to_cancel(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            status=Payment.Status.OPEN,
            total=Decimal("50.00"),
        )

        mock_client.find_payment.return_value = Mock(
            data=Mock(ecommerce_status="CANCEL")
        )

        PaymentService.sync_status(payment)

        payment.refresh_from_db()
        assert payment.status == Payment.Status.CANCEL

    def test_skips_api_call_for_completed_payment(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            status=Payment.Status.COMPLETED,
            total=Decimal("50.00"),
        )

        result = PaymentService.sync_status(payment)

        assert result == Payment.Status.COMPLETED
        mock_client.find_payment.assert_not_called()

    def test_skips_api_call_for_cancelled_payment(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            status=Payment.Status.CANCEL,
            total=Decimal("50.00"),
        )

        result = PaymentService.sync_status(payment)

        assert result == Payment.Status.CANCEL
        mock_client.find_payment.assert_not_called()

    def test_no_change_when_status_matches(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            status=Payment.Status.OPEN,
            total=Decimal("50.00"),
        )

        mock_client.find_payment.return_value = Mock(data=Mock(ecommerce_status="OPEN"))

        result = PaymentService.sync_status(payment)

        assert result == Payment.Status.OPEN

    def test_returns_local_status_on_api_error(self, mock_client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            status=Payment.Status.OPEN,
            total=Decimal("50.00"),
        )

        mock_client.find_payment.side_effect = Exception("API error")

        result = PaymentService.sync_status(payment)

        assert result == Payment.Status.OPEN


class TestUpdatePhoneNumber:
    """Test phone number updates."""

    def test_calls_api_with_correct_params(self, mock_client):
        ecommerce_id = uuid.uuid4()

        PaymentService.update_phone_number(
            ecommerce_id=ecommerce_id,
            phone_number="7879876543",
            auth_token="test-token",
        )

        mock_client.update_phone_number.assert_called_once_with(
            ecommerce_id=str(ecommerce_id),
            phone_number="7879876543",
            auth_token="test-token",
        )
