import pytest

from django_athm import models


class TestATH_Transaction:
    @pytest.mark.django_db
    def test_can_save_transaction(self):
        transaction = models.ATH_Transaction(
            reference_number="test-reference-number",
            status=models.ATH_Transaction.PROCESSING,
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        transaction.save()

        stored_transactions = models.ATH_Transaction.objects.all()
        assert len(stored_transactions) == 1
        assert stored_transactions[0].reference_number == "test-reference-number"

    def test_can_list_transactions(self):
        pass

    @pytest.mark.django_db
    def test_can_refund_transaction(self):
        transaction = models.ATH_Transaction(
            reference_number="test-reference-number",
            status=models.ATH_Transaction.PROCESSING,
            total=25.50,
            tax=1.75,
            refunded_amount=None,
            subtotal=23.75,
            metadata_1="Testing Metadata 1",
            metadata_2=None,
        )

        response = models.ATH_Transaction.refund(transaction, amount=12.80)
        assert response["refundStatus"] == "completed"

        updated_transaction = models.ATH_Transaction.objects.get(
            reference_number="test-reference-number"
        )
        assert updated_transaction.status == models.ATH_Transaction.REFUNDED
