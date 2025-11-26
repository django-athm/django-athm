from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from django_athm.models import ATHM_Item, ATHM_Transaction
from django_athm.signals import (
    athm_cancelled_response,
    athm_completed_response,
    athm_expired_response,
    athm_response_received,
)
from django_athm.views import default_callback


def create_mock_transaction_data(
    ecommerce_id="abc-123-def-456",
    reference_number="33908215-4028f9e06fd3c5c1016fdef4714a369a",
    total=Decimal("100.00"),
    sub_total=Decimal("93.00"),
    tax=Decimal("7.00"),
    fee=Decimal("2.50"),
    net_amount=Decimal("97.50"),
    ecommerce_status="COMPLETED",
    metadata1="Metadata 1",
    metadata2="Metadata 2",
    transaction_date=None,
    items=None,
):
    """Create a mock TransactionData object."""
    mock_data = MagicMock()
    mock_data.ecommerce_id = ecommerce_id
    mock_data.reference_number = reference_number
    mock_data.total = total
    mock_data.sub_total = sub_total
    mock_data.tax = tax
    mock_data.fee = fee
    mock_data.net_amount = net_amount
    mock_data.metadata1 = metadata1
    mock_data.metadata2 = metadata2
    mock_data.transaction_date = transaction_date
    mock_data.items = items

    # Mock the ecommerce_status enum
    mock_status = MagicMock()
    mock_status.value = ecommerce_status
    mock_data.ecommerce_status = mock_status if ecommerce_status else None

    return mock_data


def create_mock_verification_response(data):
    """Create a mock TransactionResponse."""
    mock_response = MagicMock()
    mock_response.data = data
    mock_response.status = (
        data.ecommerce_status.value if data.ecommerce_status else None
    )
    return mock_response


class TestDefaultCallbackView:
    """Tests for the ATH Movil callback view with server-side verification."""

    @pytest.fixture
    def mock_athm_client(self):
        """Mock ATHMovilClient for all tests."""
        with patch("django_athm.views.ATHMovilClient") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    @pytest.mark.django_db
    def test_callback_requires_ecommerce_id(self, rf):
        """Test callback returns 400 when ecommerceId is missing."""
        data = {
            "ecommerceStatus": "COMPLETED",
            # Missing ecommerceId
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 400
        assert ATHM_Transaction.objects.count() == 0

    @pytest.mark.django_db
    def test_callback_verifies_with_api(self, rf, mock_athm_client):
        """Test callback calls find_payment with ecommerceId."""
        mock_data = create_mock_transaction_data()
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        data = {"ecommerceId": "abc-123-def-456"}

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        default_callback(request)

        mock_athm_client.find_payment.assert_called_once_with(
            ecommerce_id="abc-123-def-456"
        )

    @pytest.mark.django_db
    def test_callback_verification_failure_returns_400(self, rf, mock_athm_client):
        """Test callback returns 400 when API verification fails."""
        from athm.exceptions import ATHMovilError

        mock_athm_client.find_payment.side_effect = ATHMovilError("API error")

        data = {"ecommerceId": "abc-123-def-456"}

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 400
        assert ATHM_Transaction.objects.count() == 0

    @pytest.mark.django_db
    def test_callback_uses_verified_data(self, rf, mock_athm_client):
        """Test callback creates transaction with verified API data."""
        mock_data = create_mock_transaction_data(
            reference_number="verified-ref-123",
            total=Decimal("150.00"),
            sub_total=Decimal("140.00"),
            tax=Decimal("10.00"),
            fee=Decimal("3.75"),
            net_amount=Decimal("146.25"),
            metadata1="Verified Meta 1",
            metadata2="Verified Meta 2",
        )
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        # POST data is ignored except for ecommerceId
        data = {
            "ecommerceId": "abc-123-def-456",
            "referenceNumber": "fake-ref-ignored",
            "total": "999.99",  # Should be ignored
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 201
        assert ATHM_Transaction.objects.count() == 1

        transaction = ATHM_Transaction.objects.first()
        # All data should come from verified API response, not POST
        assert transaction.reference_number == "verified-ref-123"
        assert transaction.total == Decimal("150.00")
        assert transaction.subtotal == Decimal("140.00")
        assert transaction.tax == Decimal("10.00")
        assert transaction.fee == Decimal("3.75")
        assert transaction.net_amount == Decimal("146.25")
        assert transaction.metadata_1 == "Verified Meta 1"
        assert transaction.metadata_2 == "Verified Meta 2"
        assert transaction.status == ATHM_Transaction.Status.COMPLETED

    @pytest.mark.django_db
    def test_callback_intermediate_status_open(self, rf):
        """Test callback returns 200 for OPEN status without verification."""
        data = {
            "ecommerceStatus": "OPEN",
            "ecommerceId": "abc-123",
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        # Should return 200 OK without creating transaction or calling API
        assert response.status_code == 200
        assert ATHM_Transaction.objects.count() == 0

    @pytest.mark.django_db
    def test_callback_intermediate_status_confirm(self, rf):
        """Test callback returns 200 for CONFIRM status without verification."""
        data = {
            "ecommerceStatus": "CONFIRM",
            "ecommerceId": "abc-123",
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 200
        assert ATHM_Transaction.objects.count() == 0

    @pytest.mark.django_db
    def test_callback_missing_reference_number_returns_400(self, rf, mock_athm_client):
        """Test callback returns 400 when API returns no reference_number."""
        mock_data = create_mock_transaction_data(reference_number=None)
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        data = {"ecommerceId": "abc-123-def-456"}

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 400
        assert ATHM_Transaction.objects.count() == 0

    @pytest.mark.django_db
    def test_callback_status_mapping(self, rf, mock_athm_client):
        """Test ecommerceStatus to internal status mapping."""
        status_mapping = {
            "COMPLETED": ATHM_Transaction.Status.COMPLETED,
            "CANCEL": ATHM_Transaction.Status.CANCEL,
            "EXPIRED": ATHM_Transaction.Status.CANCEL,
            "REFUNDED": ATHM_Transaction.Status.REFUNDED,
        }

        for api_status, expected_status in status_mapping.items():
            ATHM_Transaction.objects.all().delete()

            mock_data = create_mock_transaction_data(
                reference_number=f"ref-{api_status.lower()}",
                ecommerce_status=api_status,
            )
            mock_athm_client.find_payment.return_value = (
                create_mock_verification_response(mock_data)
            )

            data = {"ecommerceId": f"ecom-{api_status.lower()}"}

            url = reverse("django_athm:athm_callback")
            request = rf.post(url, data=data)
            response = default_callback(request)

            assert response.status_code == 201
            transaction = ATHM_Transaction.objects.first()
            assert transaction.status == expected_status, f"Failed for {api_status}"

    @pytest.mark.django_db
    def test_callback_idempotent_duplicate_reference(self, rf, mock_athm_client):
        """Test callback is idempotent - duplicate reference_number returns 200."""
        mock_data = create_mock_transaction_data(
            reference_number="ref-idempotent",
            total=Decimal("50.00"),
        )
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        data = {"ecommerceId": "abc-123"}

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 201
        assert ATHM_Transaction.objects.count() == 1

        # Second callback with updated data
        mock_data_updated = create_mock_transaction_data(
            reference_number="ref-idempotent",
            total=Decimal("75.00"),
        )
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data_updated
        )

        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 200  # Updated, not created
        assert ATHM_Transaction.objects.count() == 1

        transaction = ATHM_Transaction.objects.first()
        assert transaction.total == Decimal("75.00")

    @pytest.mark.django_db
    def test_callback_with_items(self, rf, mock_athm_client):
        """Test callback creates items from verified API response."""
        mock_item = MagicMock()
        mock_item.name = "Test Item"
        mock_item.description = "Test Description"
        mock_item.quantity = 2
        mock_item.price = Decimal("50.00")
        mock_item.tax = Decimal("5.00")
        mock_item.metadata = "item-meta"

        mock_data = create_mock_transaction_data(items=[mock_item])
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        data = {"ecommerceId": "abc-123"}

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 201
        assert ATHM_Item.objects.count() == 1

        item = ATHM_Item.objects.first()
        assert item.name == "Test Item"
        assert item.description == "Test Description"
        assert item.quantity == 2
        assert item.price == Decimal("50.00")
        assert item.tax == Decimal("5.00")
        assert item.metadata == "item-meta"

    @pytest.mark.django_db
    def test_callback_completed_signal_dispatched(self, rf, mock_athm_client):
        """Test athm_completed_response signal is dispatched for COMPLETED status."""
        handler = MagicMock()
        athm_completed_response.connect(handler)

        try:
            mock_data = create_mock_transaction_data(ecommerce_status="COMPLETED")
            mock_athm_client.find_payment.return_value = (
                create_mock_verification_response(mock_data)
            )

            data = {"ecommerceId": "abc-123"}

            url = reverse("django_athm:athm_callback")
            request = rf.post(url, data=data)
            default_callback(request)

            assert handler.called
            assert handler.call_count == 1
        finally:
            athm_completed_response.disconnect(handler)

    @pytest.mark.django_db
    def test_callback_expired_signal_dispatched(self, rf, mock_athm_client):
        """Test athm_expired_response signal is dispatched for EXPIRED status."""
        handler = MagicMock()
        athm_expired_response.connect(handler)

        try:
            mock_data = create_mock_transaction_data(
                reference_number="ref-expired",
                ecommerce_status="EXPIRED",
            )
            mock_athm_client.find_payment.return_value = (
                create_mock_verification_response(mock_data)
            )

            data = {"ecommerceId": "abc-123"}

            url = reverse("django_athm:athm_callback")
            request = rf.post(url, data=data)
            default_callback(request)

            assert handler.called
            assert handler.call_count == 1
        finally:
            athm_expired_response.disconnect(handler)

    @pytest.mark.django_db
    def test_callback_cancelled_signal_dispatched(self, rf, mock_athm_client):
        """Test athm_cancelled_response signal is dispatched for CANCEL status."""
        handler = MagicMock()
        athm_cancelled_response.connect(handler)

        try:
            mock_data = create_mock_transaction_data(
                reference_number="ref-cancel",
                ecommerce_status="CANCEL",
            )
            mock_athm_client.find_payment.return_value = (
                create_mock_verification_response(mock_data)
            )

            data = {"ecommerceId": "abc-123"}

            url = reverse("django_athm:athm_callback")
            request = rf.post(url, data=data)
            default_callback(request)

            assert handler.called
            assert handler.call_count == 1
        finally:
            athm_cancelled_response.disconnect(handler)

    @pytest.mark.django_db
    def test_callback_response_received_signal_dispatched(self, rf, mock_athm_client):
        """Test athm_response_received signal is always dispatched."""
        handler = MagicMock()
        athm_response_received.connect(handler)

        try:
            mock_data = create_mock_transaction_data()
            mock_athm_client.find_payment.return_value = (
                create_mock_verification_response(mock_data)
            )

            data = {"ecommerceId": "abc-123"}

            url = reverse("django_athm:athm_callback")
            request = rf.post(url, data=data)
            default_callback(request)

            assert handler.called
        finally:
            athm_response_received.disconnect(handler)

    @pytest.mark.django_db
    def test_callback_with_transaction_date(self, rf, mock_athm_client):
        """Test callback uses transaction_date from API response."""
        test_date = datetime(2024, 6, 15, 14, 30, 0)
        mock_data = create_mock_transaction_data(transaction_date=test_date)
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        data = {"ecommerceId": "abc-123"}

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 201
        transaction = ATHM_Transaction.objects.first()
        assert transaction.date.year == 2024
        assert transaction.date.month == 6
        assert transaction.date.day == 15

    @pytest.mark.django_db
    def test_callback_items_replaced_on_update(self, rf, mock_athm_client):
        """Test items are replaced, not duplicated, on duplicate callback."""
        mock_item1 = MagicMock()
        mock_item1.name = "Item 1"
        mock_item1.description = ""
        mock_item1.quantity = 1
        mock_item1.price = Decimal("50.00")
        mock_item1.tax = None
        mock_item1.metadata = None

        mock_data = create_mock_transaction_data(
            reference_number="ref-items-replace",
            items=[mock_item1],
        )
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        data = {"ecommerceId": "abc-123"}
        url = reverse("django_athm:athm_callback")

        # First callback
        request = rf.post(url, data=data)
        default_callback(request)
        assert ATHM_Item.objects.count() == 1

        # Second callback with different item
        mock_item2 = MagicMock()
        mock_item2.name = "Item 2"
        mock_item2.description = ""
        mock_item2.quantity = 2
        mock_item2.price = Decimal("25.00")
        mock_item2.tax = None
        mock_item2.metadata = None

        mock_data_updated = create_mock_transaction_data(
            reference_number="ref-items-replace",
            items=[mock_item2],
        )
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data_updated
        )

        request = rf.post(url, data=data)
        default_callback(request)

        # Should have 1 item (replaced, not added)
        assert ATHM_Item.objects.count() == 1
        item = ATHM_Item.objects.first()
        assert item.name == "Item 2"
        assert item.quantity == 2
