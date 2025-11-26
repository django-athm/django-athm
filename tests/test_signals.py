from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from django_athm import models, signals


def create_mock_transaction_data(
    reference_number="test-ref",
    total=Decimal("100.00"),
    ecommerce_status="COMPLETED",
):
    """Create a mock TransactionData object."""
    mock_data = MagicMock()
    mock_data.ecommerce_id = "test-ecommerce-id"
    mock_data.reference_number = reference_number
    mock_data.total = total
    mock_data.sub_total = None
    mock_data.tax = None
    mock_data.fee = None
    mock_data.net_amount = None
    mock_data.metadata1 = None
    mock_data.metadata2 = None
    mock_data.transaction_date = None
    mock_data.items = None

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


@pytest.mark.django_db
class TestViewSignalDispatch:
    """Test signals dispatched from the callback view."""

    @pytest.fixture
    def mock_athm_client(self):
        """Mock ATHMovilClient for all tests."""
        with patch("django_athm.views.ATHMovilClient") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    def test_completed_signal_dispatched_on_completed_status(
        self, rf, mock_athm_client
    ):
        """Test that completed signal is dispatched when transaction is completed."""
        received = {"called": False, "transaction": None}

        def handler(sender, transaction, **kwargs):
            received["called"] = True
            received["transaction"] = transaction

        mock_data = create_mock_transaction_data(
            reference_number="test-completed-signal",
            ecommerce_status="COMPLETED",
        )
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        signals.athm_completed_response.connect(handler)
        try:
            from django_athm.views import default_callback

            request = rf.post(
                "/callback/",
                data={"ecommerceId": "test-ecommerce-id"},
            )
            response = default_callback(request)
            assert response.status_code == 201
            assert received["called"] is True
            assert received["transaction"].reference_number == "test-completed-signal"
        finally:
            signals.athm_completed_response.disconnect(handler)

    def test_cancelled_signal_dispatched_on_cancel_status(self, rf, mock_athm_client):
        """Test that cancelled signal is dispatched when transaction is cancelled."""
        received = {"called": False, "transaction": None}

        def handler(sender, transaction, **kwargs):
            received["called"] = True
            received["transaction"] = transaction

        mock_data = create_mock_transaction_data(
            reference_number="test-cancelled-signal",
            ecommerce_status="CANCEL",
        )
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        signals.athm_cancelled_response.connect(handler)
        try:
            from django_athm.views import default_callback

            request = rf.post(
                "/callback/",
                data={"ecommerceId": "test-ecommerce-id"},
            )
            response = default_callback(request)
            assert response.status_code == 201
            assert received["called"] is True
            assert received["transaction"].reference_number == "test-cancelled-signal"
        finally:
            signals.athm_cancelled_response.disconnect(handler)

    def test_general_response_signal_always_dispatched(self, rf, mock_athm_client):
        """Test that general response signal is always dispatched from view."""
        received = {"called": False, "transaction": None}

        def handler(sender, transaction, **kwargs):
            received["called"] = True
            received["transaction"] = transaction

        mock_data = create_mock_transaction_data(
            reference_number="test-general-signal",
            total=Decimal("50.00"),
        )
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        signals.athm_response_received.connect(handler)
        try:
            from django_athm.views import default_callback

            request = rf.post(
                "/callback/",
                data={"ecommerceId": "test-ecommerce-id"},
            )
            response = default_callback(request)
            assert response.status_code == 201
            assert received["called"] is True
            assert received["transaction"].reference_number == "test-general-signal"
        finally:
            signals.athm_response_received.disconnect(handler)

    def test_signal_contains_transaction_object(self, rf, mock_athm_client):
        """Test that signal provides the transaction object."""
        received = {"transaction": None}

        def handler(sender, transaction, **kwargs):
            received["transaction"] = transaction

        mock_data = create_mock_transaction_data(
            reference_number="test-txn-object",
            total=Decimal("75.00"),
            ecommerce_status="COMPLETED",
        )
        mock_athm_client.find_payment.return_value = create_mock_verification_response(
            mock_data
        )

        signals.athm_response_received.connect(handler)
        try:
            from django_athm.views import default_callback

            request = rf.post(
                "/callback/",
                data={"ecommerceId": "test-ecommerce-id"},
            )
            response = default_callback(request)
            assert response.status_code == 201
            assert received["transaction"] is not None
            assert isinstance(received["transaction"], models.ATHM_Transaction)
            assert received["transaction"].total == Decimal("75.00")
        finally:
            signals.athm_response_received.disconnect(handler)
