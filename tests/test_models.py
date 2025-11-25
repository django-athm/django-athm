import pytest
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from django_athm import models
from django_athm.constants import (
    CANCEL_PAYMENT_URL,
    FIND_PAYMENT_URL,
    REFUND_URL,
    REPORT_URL,
    SEARCH_URL,
    TransactionStatus,
)
from django_athm.exceptions import ATHM_RefundError

pytestmark = pytest.mark.django_db


class TestATHM_Transaction:
    """Tests for ATHM_Transaction model basic CRUD operations."""

    def test_can_save_transaction(self):
        transaction = models.ATHM_Transaction(
            reference_number="test-reference-number",
            status=models.ATHM_Transaction.Status.OPEN,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        transaction.save()

        stored_transactions = models.ATHM_Transaction.objects.all()
        assert len(stored_transactions) == 1
        assert stored_transactions[0].reference_number == "test-reference-number"

    def test_can_save_transaction_with_v4_fields(self):
        """Test saving transaction with v4 API fields."""
        transaction = models.ATHM_Transaction.objects.create(
            reference_number="test-v4-reference",
            status=models.ATHM_Transaction.Status.COMPLETED,
            date=timezone.now(),
            total=100.00,
            tax=7.00,
            subtotal=93.00,
            fee=2.50,
            net_amount=97.50,
            ecommerce_id="ecom-123-456",
            ecommerce_status="COMPLETED",
            customer_name="John Doe",
            customer_phone="+17875551234",
        )

        stored = models.ATHM_Transaction.objects.get(pk=transaction.pk)
        assert stored.ecommerce_id == "ecom-123-456"
        assert stored.ecommerce_status == "COMPLETED"
        assert stored.fee == 2.50
        assert stored.net_amount == 97.50
        assert stored.customer_name == "John Doe"
        assert stored.customer_phone == "+17875551234"

    def test_str_representation(self):
        transaction = models.ATHM_Transaction.objects.create(
            reference_number="test-reference-number",
            status=models.ATHM_Transaction.Status.OPEN,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        assert str(transaction) == "test-reference-number"


class TestATHM_TransactionRefund:
    """Tests for ATHM_Transaction refund functionality."""

    def test_can_refund_transaction(self, mock_http_adapter_post):
        mock_http_adapter_post.return_value.json.return_value = {
            "refundStatus": TransactionStatus.completed.value,
            "refundedAmount": "12.80",
        }

        transaction = models.ATHM_Transaction.objects.create(
            reference_number="test-reference-number",
            status=models.ATHM_Transaction.Status.OPEN,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        response = models.ATHM_Transaction.refund(transaction, amount=12.80)
        assert response["refundStatus"] == TransactionStatus.completed.value

        transaction.refresh_from_db()
        assert transaction.status == models.ATHM_Transaction.Status.REFUNDED
        mock_http_adapter_post.assert_called_once_with(
            REFUND_URL,
            data={
                "privateToken": "private-token",
                "publicToken": "public-token",
                "referenceNumber": "test-reference-number",
                "amount": "12.8",
            },
        )

    def test_fail_to_refund_transaction(self, mock_http_adapter_post):
        mock_http_adapter_post.return_value.json.return_value = {
            "errorCode": "5010",
            "description": "Transaction does not exist",
        }

        transaction = models.ATHM_Transaction.objects.create(
            reference_number="test-reference-number",
            status=models.ATHM_Transaction.Status.OPEN,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        with pytest.raises(ATHM_RefundError):
            models.ATHM_Transaction.refund(transaction, amount=12.80)

        transaction.refresh_from_db()
        assert transaction.status == models.ATHM_Transaction.Status.OPEN
        mock_http_adapter_post.assert_called_once_with(
            REFUND_URL,
            data={
                "privateToken": "private-token",
                "publicToken": "public-token",
                "referenceNumber": "test-reference-number",
                "amount": "12.8",
            },
        )

    def test_uses_total_if_no_amount(self, mock_http_adapter_post):
        mock_http_adapter_post.return_value.json.return_value = {
            "refundStatus": TransactionStatus.completed.value,
            "refundedAmount": "25.50",
        }

        transaction = models.ATHM_Transaction.objects.create(
            reference_number="test-reference-number",
            status=models.ATHM_Transaction.Status.OPEN,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        models.ATHM_Transaction.refund(transaction)

        mock_http_adapter_post.assert_called_once_with(
            REFUND_URL,
            data={
                "privateToken": "private-token",
                "publicToken": "public-token",
                "referenceNumber": "test-reference-number",
                "amount": "25.5",
            },
        )


class TestATHM_TransactionAPIMethodsV4:
    """Tests for ATHM_Transaction v4 API methods."""

    def test_find_payment(self, mock_http_adapter_post):
        """Test find_payment calls correct endpoint."""
        mock_http_adapter_post.return_value.json.return_value = {
            "status": "success",
            "data": {
                "ecommerceStatus": "COMPLETED",
                "ecommerceId": "ecom-123",
                "referenceNumber": "ref-123",
            },
        }

        response = models.ATHM_Transaction.find_payment("ecom-123")

        assert response["status"] == "success"
        mock_http_adapter_post.assert_called_once_with(
            FIND_PAYMENT_URL,
            data={
                "ecommerceId": "ecom-123",
                "publicToken": "public-token",
            },
        )

    def test_find_payment_with_custom_token(self, mock_http_adapter_post):
        """Test find_payment with custom public token."""
        mock_http_adapter_post.return_value.json.return_value = {"status": "success"}

        models.ATHM_Transaction.find_payment("ecom-123", public_token="custom-token")

        mock_http_adapter_post.assert_called_once_with(
            FIND_PAYMENT_URL,
            data={
                "ecommerceId": "ecom-123",
                "publicToken": "custom-token",
            },
        )

    def test_cancel_payment(self, mock_http_adapter_post):
        """Test cancel_payment calls correct endpoint."""
        mock_http_adapter_post.return_value.json.return_value = {
            "status": "success",
            "data": {"ecommerceStatus": "CANCEL"},
        }

        response = models.ATHM_Transaction.cancel_payment("ecom-456")

        assert response["status"] == "success"
        mock_http_adapter_post.assert_called_once_with(
            CANCEL_PAYMENT_URL,
            data={
                "ecommerceId": "ecom-456",
                "publicToken": "public-token",
            },
        )

    def test_search_transaction(self, mock_http_adapter_post):
        """Test search calls correct endpoint with transaction."""
        mock_http_adapter_post.return_value.json.return_value = {
            "referenceNumber": "ref-search-test",
            "total": "50.00",
        }

        transaction = models.ATHM_Transaction.objects.create(
            reference_number="ref-search-test",
            status=models.ATHM_Transaction.Status.COMPLETED,
            date=timezone.now(),
            total=50.00,
        )

        response = models.ATHM_Transaction.search(transaction)

        assert response["referenceNumber"] == "ref-search-test"
        mock_http_adapter_post.assert_called_once_with(
            SEARCH_URL,
            data={
                "publicToken": "public-token",
                "privateToken": "private-token",
                "referenceNumber": "ref-search-test",
            },
        )

    def test_get_report(self, mock_http_adapter_get_with_data):
        """Test get_report calls correct endpoint."""
        # get_with_data returns response.json() directly
        mock_http_adapter_get_with_data.return_value = [
            {"referenceNumber": "ref-1", "total": "100.00"},
            {"referenceNumber": "ref-2", "total": "200.00"},
        ]

        response = models.ATHM_Transaction.get_report(
            start_date="2025-01-01 00:00:00",
            end_date="2025-01-31 23:59:59",
        )

        assert len(response) == 2
        mock_http_adapter_get_with_data.assert_called_once_with(
            url=REPORT_URL,
            data={
                "publicToken": "public-token",
                "privateToken": "private-token",
                "fromDate": "2025-01-01 00:00:00",
                "toDate": "2025-01-31 23:59:59",
            },
        )


class TestATHM_TransactionQuerySet:
    """Tests for ATHM_Transaction QuerySet managers."""

    @pytest.fixture
    def sample_transactions(self):
        """Create sample transactions with various statuses."""
        now = timezone.now()
        client = models.ATHM_Client.objects.create(
            name="Test Client",
            phone_number="+17875551234",
        )

        completed = models.ATHM_Transaction.objects.create(
            reference_number="completed-ref",
            status=models.ATHM_Transaction.Status.COMPLETED,
            date=now,
            total=100.00,
            client=client,
        )
        # Add item to completed transaction
        models.ATHM_Item.objects.create(
            transaction=completed,
            name="Test Item",
            price=100.00,
            quantity=1,
        )

        refunded = models.ATHM_Transaction.objects.create(
            reference_number="refunded-ref",
            status=models.ATHM_Transaction.Status.REFUNDED,
            date=now,
            total=50.00,
            refunded_amount=50.00,
        )

        cancelled = models.ATHM_Transaction.objects.create(
            reference_number="cancelled-ref",
            status=models.ATHM_Transaction.Status.CANCEL,
            date=now,
            total=25.00,
        )

        open_tx = models.ATHM_Transaction.objects.create(
            reference_number="open-ref",
            status=models.ATHM_Transaction.Status.OPEN,
            date=now,
            total=75.00,
        )

        confirm = models.ATHM_Transaction.objects.create(
            reference_number="confirm-ref",
            status=models.ATHM_Transaction.Status.CONFIRM,
            date=now,
            total=30.00,
        )

        return {
            "completed": completed,
            "refunded": refunded,
            "cancelled": cancelled,
            "open": open_tx,
            "confirm": confirm,
            "client": client,
        }

    def test_completed_queryset(self, sample_transactions):
        """Test .completed() returns only completed transactions."""
        completed = models.ATHM_Transaction.objects.completed()
        assert completed.count() == 1
        assert completed.first().reference_number == "completed-ref"

    def test_refundable_queryset(self, sample_transactions):
        """Test .refundable() returns completed transactions without refund."""
        refundable = models.ATHM_Transaction.objects.refundable()
        assert refundable.count() == 1
        assert refundable.first().reference_number == "completed-ref"

    def test_refunded_queryset(self, sample_transactions):
        """Test .refunded() returns only refunded transactions."""
        refunded = models.ATHM_Transaction.objects.refunded()
        assert refunded.count() == 1
        assert refunded.first().reference_number == "refunded-ref"

    def test_pending_queryset(self, sample_transactions):
        """Test .pending() returns OPEN and CONFIRM status transactions."""
        pending = models.ATHM_Transaction.objects.pending()
        assert pending.count() == 2
        refs = set(t.reference_number for t in pending)
        assert refs == {"open-ref", "confirm-ref"}

    def test_with_items_queryset(self, sample_transactions):
        """Test .with_items() prefetches related items."""
        with_items = models.ATHM_Transaction.objects.with_items()
        # Get the completed transaction which has an item
        tx = with_items.get(reference_number="completed-ref")
        # Access items without additional query (prefetched)
        assert tx.items.count() == 1
        assert tx.items.first().name == "Test Item"

    def test_with_client_queryset(self, sample_transactions):
        """Test .with_client() selects related client."""
        with_client = models.ATHM_Transaction.objects.with_client()
        tx = with_client.get(reference_number="completed-ref")
        # Access client without additional query (selected)
        assert tx.client.name == "Test Client"


class TestATHM_TransactionProperties:
    """Tests for ATHM_Transaction model properties."""

    def test_is_refundable_property_completed_no_refund(self):
        """Test is_refundable returns True for completed without refund."""
        transaction = models.ATHM_Transaction.objects.create(
            reference_number="refundable-test",
            status=models.ATHM_Transaction.Status.COMPLETED,
            date=timezone.now(),
            total=100.00,
            refunded_amount=None,
        )
        assert transaction.is_refundable is True

    def test_is_refundable_property_already_refunded(self):
        """Test is_refundable returns False for refunded transaction."""
        transaction = models.ATHM_Transaction.objects.create(
            reference_number="already-refunded",
            status=models.ATHM_Transaction.Status.REFUNDED,
            date=timezone.now(),
            total=100.00,
            refunded_amount=100.00,
        )
        assert transaction.is_refundable is False

    def test_is_completed_property(self):
        """Test is_completed returns correct value."""
        completed = models.ATHM_Transaction.objects.create(
            reference_number="completed-prop",
            status=models.ATHM_Transaction.Status.COMPLETED,
            date=timezone.now(),
            total=100.00,
        )
        assert completed.is_completed is True

        open_tx = models.ATHM_Transaction.objects.create(
            reference_number="open-prop",
            status=models.ATHM_Transaction.Status.OPEN,
            date=timezone.now(),
            total=50.00,
        )
        assert open_tx.is_completed is False

    def test_is_pending_property(self):
        """Test is_pending returns correct value for OPEN/CONFIRM status."""
        open_tx = models.ATHM_Transaction.objects.create(
            reference_number="pending-open",
            status=models.ATHM_Transaction.Status.OPEN,
            date=timezone.now(),
            total=50.00,
        )
        assert open_tx.is_pending is True

        confirm_tx = models.ATHM_Transaction.objects.create(
            reference_number="pending-confirm",
            status=models.ATHM_Transaction.Status.CONFIRM,
            date=timezone.now(),
            total=50.00,
        )
        assert confirm_tx.is_pending is True

        completed = models.ATHM_Transaction.objects.create(
            reference_number="not-pending",
            status=models.ATHM_Transaction.Status.COMPLETED,
            date=timezone.now(),
            total=100.00,
        )
        assert completed.is_pending is False


class TestATHM_Client:
    """Tests for ATHM_Client model."""

    def test_client_creation(self):
        """Test basic client creation."""
        client = models.ATHM_Client.objects.create(
            name="Test Client",
            email="test@example.com",
            phone_number="+17875551234",
        )

        assert client.name == "Test Client"
        assert client.email == "test@example.com"
        assert client.phone_number == "+17875551234"
        assert client.pk is not None

    def test_client_str_representation(self):
        """Test client string representation."""
        client = models.ATHM_Client.objects.create(
            name="John Doe",
            phone_number="+17875551234",
        )
        assert str(client) == "John Doe"

    def test_client_with_transactions_queryset(self):
        """Test .with_transactions() prefetches transactions."""
        client = models.ATHM_Client.objects.create(
            name="Client With Transactions",
            phone_number="+17871234567",
        )
        # Create transactions for this client
        models.ATHM_Transaction.objects.create(
            reference_number="client-tx-1",
            status=models.ATHM_Transaction.Status.COMPLETED,
            date=timezone.now(),
            total=100.00,
            client=client,
        )
        models.ATHM_Transaction.objects.create(
            reference_number="client-tx-2",
            status=models.ATHM_Transaction.Status.COMPLETED,
            date=timezone.now(),
            total=50.00,
            client=client,
        )

        # Use the with_transactions manager
        client_with_tx = models.ATHM_Client.objects.with_transactions().get(
            pk=client.pk
        )
        # Transactions should be prefetched
        assert client_with_tx.transactions.count() == 2


class TestATHM_Item:
    """Tests for ATHM_Item model."""

    def test_item_creation(self):
        """Test basic item creation."""
        transaction = models.ATHM_Transaction.objects.create(
            reference_number="item-test-tx",
            status=models.ATHM_Transaction.Status.COMPLETED,
            date=timezone.now(),
            total=100.00,
        )

        item = models.ATHM_Item.objects.create(
            transaction=transaction,
            name="Test Product",
            description="A test product description",
            quantity=2,
            price=50.00,
            tax=3.50,
            metadata="item metadata",
        )

        assert item.name == "Test Product"
        assert item.quantity == 2
        assert item.price == 50.00
        assert item.tax == 3.50
        assert item.transaction == transaction

    def test_item_str_representation(self):
        """Test item string representation."""
        transaction = models.ATHM_Transaction.objects.create(
            reference_number="item-str-tx",
            status=models.ATHM_Transaction.Status.COMPLETED,
            date=timezone.now(),
            total=25.00,
        )

        item = models.ATHM_Item.objects.create(
            transaction=transaction,
            name="Widget",
            quantity=1,
            price=25.00,
        )

        assert str(item) == "Widget"
