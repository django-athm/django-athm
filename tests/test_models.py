import pytest

from django_athm import models


class TestATHM_Transaction:
    @pytest.mark.django_db
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

    def test_can_list_transactions(self):
        pass

    @pytest.mark.django_db
    def test_can_refund_transaction(self):
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
        assert response["refundStatus"] == "completed"

        updated_transaction = models.ATHM_Transaction.objects.get(
            reference_number="test-reference-number"
        )
        assert updated_transaction.status == models.ATHM_Transaction.REFUNDED

    @pytest.mark.django_db
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

    @pytest.mark.django_db
    def test_uses_total_if_no_amount(self):
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

        response = models.ATHM_Transaction.refund(transaction)
        assert response["data"].get("amount") == "25.5"