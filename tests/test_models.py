import pytest

from django_athm import models
from django_athm.constants import COMPLETED_STATUS, REFUND_URL
from django_athm.exceptions import ATHM_RefundError

pytestmark = pytest.mark.django_db


class TestATHM_Transaction:
    def test_can_save_transaction(self):
        transaction = models.ATHM_Transaction(
            reference_number="test-reference-number",
            status=models.ATHM_Transaction.PROCESSING,
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

    def test_can_refund_transaction(self, mock_http_adapter_post):
        mock_http_adapter_post.return_value = {
            "refundStatus": COMPLETED_STATUS,
            "refundedAmount": "12.80",
        }

        transaction = models.ATHM_Transaction(
            reference_number="test-reference-number",
            status=models.ATHM_Transaction.PROCESSING,
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        response = models.ATHM_Transaction.refund(transaction, amount=12.80)
        assert response["refundStatus"] == COMPLETED_STATUS

        transaction.refresh_from_db()
        assert transaction.status == models.ATHM_Transaction.REFUNDED
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
        mock_http_adapter_post.return_value = {
            "errorCode": "5010",
            "description": "Transaction does not exist",
        }

        transaction = models.ATHM_Transaction.objects.create(
            reference_number="test-reference-number",
            status=models.ATHM_Transaction.PROCESSING,
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
        assert transaction.status == models.ATHM_Transaction.PROCESSING
        mock_http_adapter_post.assert_called_once_with(
            REFUND_URL,
            data={
                "privateToken": "private-token",
                "publicToken": "public-token",
                "referenceNumber": "test-reference-number",
                "amount": "12.8",
            },
        )

    def test_str_representation(self):
        transaction = models.ATHM_Transaction.objects.create(
            reference_number="test-reference-number",
            status=models.ATHM_Transaction.PROCESSING,
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        assert str(transaction) == "test-reference-number"

    def test_uses_total_if_no_amount(self, mock_http_adapter_post):
        mock_http_adapter_post.return_value = {
            "refundStatus": COMPLETED_STATUS,
            "refundedAmount": "25.50",
        }

        transaction = models.ATHM_Transaction.objects.create(
            reference_number="test-reference-number",
            status=models.ATHM_Transaction.PROCESSING,
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
