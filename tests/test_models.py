import pytest
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from django_athm import models
from django_athm.exceptions import ATHM_RefundError

pytestmark = pytest.mark.django_db


class TestATHM_Transaction:
    def test_can_save_transaction(self):
        transaction = models.Payment(
            reference_number="test-reference-number",
            status=models.Payment.Status.OPEN,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        transaction.save()

        stored_transactions = models.Payment.objects.all()
        assert len(stored_transactions) == 1
        assert stored_transactions[0].reference_number == "test-reference-number"

    def test_can_refund_transaction(self, mocker):
        mock_client = mocker.patch("django_athm.client.ATHMClient")
        mock_instance = mock_client.return_value
        mock_instance.refund_payment.return_value = {
            "refundStatus": "COMPLETED",
            "refundedAmount": "12.80",
        }

        transaction = models.Payment.objects.create(
            reference_number="test-reference-number",
            status=models.Payment.Status.OPEN,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        response = models.Payment.refund(transaction, amount=12.80)
        assert response["refundStatus"] == "COMPLETED"

        transaction.refresh_from_db()
        assert transaction.status == models.Payment.Status.REFUNDED
        mock_instance.refund_payment.assert_called_once()

    def test_fail_to_refund_transaction(self, mocker):
        mock_client = mocker.patch("django_athm.client.ATHMClient")
        mock_instance = mock_client.return_value
        mock_instance.refund_payment.side_effect = Exception(
            "Transaction does not exist"
        )

        transaction = models.Payment.objects.create(
            reference_number="test-reference-number",
            status=models.Payment.Status.OPEN,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        with pytest.raises(ATHM_RefundError):
            models.Payment.refund(transaction, amount=12.80)

        transaction.refresh_from_db()
        assert transaction.status == models.Payment.Status.OPEN
        mock_instance.refund_payment.assert_called_once()

    def test_str_representation(self):
        transaction = models.Payment.objects.create(
            reference_number="test-reference-number",
            status=models.Payment.Status.OPEN,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        assert str(transaction) == "test-reference-number"

    def test_uses_total_if_no_amount(self, mocker):
        mock_client = mocker.patch("django_athm.client.ATHMClient")
        mock_instance = mock_client.return_value
        mock_instance.refund_payment.return_value = {
            "refundStatus": "COMPLETED",
            "refundedAmount": "25.50",
        }

        transaction = models.Payment.objects.create(
            reference_number="test-reference-number",
            status=models.Payment.Status.OPEN,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        models.Payment.refund(transaction)

        # Verify refund_payment was called with the full total amount
        mock_instance.refund_payment.assert_called_once_with(
            reference_number="test-reference-number",
            amount=25.50,  # Should use transaction.total
        )
