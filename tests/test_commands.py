from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from django_athm.constants import COMPLETED_STATUS, EXPIRED_STATUS, REFUNDED_STATUS
from django_athm.management.commands.athm_sync import get_status
from django_athm.models import ATHM_Item, ATHM_Transaction


class TestSyncCommand:
    def test_get_status_refund(self):
        upstream_transaction = {
            "transactionType": "refund",
            "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
            "date": "2019-06-06 17:12:02.0",
            "refundedAmount": "1.00",
            "total": "1.00",
            "tax": "1.00",
            "subtotal": "1.00",
            "metadata1": "metadata1 test",
            "metadata2": "metadata2 test",
            "items": [],
        }

        status = get_status(upstream_transaction)
        assert status == REFUNDED_STATUS

    def test_get_status_ecommerce_refund(self):
        upstream_transaction = {
            "transactionType": "ecommerce",
            "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
            "date": "2019-06-06 17:12:02.0",
            "refundedAmount": "1.00",
            "total": "1.00",
            "tax": "1.00",
            "subtotal": "1.00",
            "metadata1": "metadata1 test",
            "metadata2": "metadata2 test",
            "items": [],
        }

        status = get_status(upstream_transaction)
        assert status == REFUNDED_STATUS

    def test_get_status_ecommerce_non_refund(self):
        upstream_transaction = {
            "transactionType": "ecommerce",
            "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
            "date": "2019-06-06 17:12:02.0",
            "refundedAmount": "0.00",
            "total": "1.00",
            "tax": "1.00",
            "subtotal": "1.00",
            "metadata1": "metadata1 test",
            "metadata2": "metadata2 test",
            "items": [],
        }

        status = get_status(upstream_transaction)
        assert status == COMPLETED_STATUS

    def test_get_status_other(self):
        upstream_transaction = {
            "status": EXPIRED_STATUS,
            "transactionType": "expired",
            "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
            "date": "2019-06-06 17:12:02.0",
            "refundedAmount": "1.00",
            "total": "1.00",
            "tax": "1.00",
            "subtotal": "1.00",
            "metadata1": "metadata1 test",
            "metadata2": "metadata2 test",
            "items": [],
        }

        status = get_status(upstream_transaction)
        assert status == EXPIRED_STATUS

    @pytest.mark.django_db
    def test_command_output(self, mock_http_adapter_get_with_data):
        mock_http_adapter_get_with_data.return_value = [
            {
                "transactionType": "refund",
                "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
                "date": "2019-06-06 17:12:02.0",
                "refundedAmount": "1.00",
                "total": "1.00",
                "tax": "1.00",
                "subtotal": "1.00",
                "metadata1": "metadata1 test",
                "metadata2": "metadata2 test",
                "items": [
                    {
                        "name": "First Item",
                        "description": "This is a description.",
                        "quantity": "1",
                        "price": "1.00",
                        "tax": "1.00",
                        "metadata": "metadata test",
                    },
                    {
                        "name": "Second Item",
                        "description": "This is another description.",
                        "quantity": "1",
                        "price": "1.00",
                        "tax": "1.00",
                        "metadata": "metadata test",
                    },
                ],
            },
            {
                "transactionType": "payment",
                "status": "completed",
                "referenceNumber": "212831546-402894d56b240610016b2e6c78a6003a",
                "date": "2019-06-06 16:12:02.0",
                "refundedAmount": "0.00",
                "total": "5.00",
                "tax": "1.00",
                "subtotal": "4.00",
                "metadata1": "metadata1 test",
                "metadata2": "metadata2 test",
                "items": [
                    {
                        "name": "First Item",
                        "description": "This is a description.",
                        "quantity": "1",
                        "price": "1.00",
                        "tax": "1.00",
                        "metadata": "metadata test",
                    },
                    {
                        "name": "Second Item",
                        "description": "This is another description.",
                        "quantity": "1",
                        "price": "1.00",
                        "tax": "1.00",
                        "metadata": "metadata test",
                    },
                ],
            },
        ]

        existing_transaction = ATHM_Transaction.objects.create(
            status="completed",
            reference_number="212831546-402894d56b240610016b2e6c78a6003a",
            date=make_aware(parse_datetime("2019-06-06 16:12:02.0")),
            refunded_amount=0.00,
            total=5.00,
            tax=1.00,
            subtotal=4.00,
            metadata_1="metadata1 test",
            metadata_2="metadata2 test",
        )

        ATHM_Item.objects.create(
            name="First Item",
            transaction=existing_transaction,
            description="This is a description.",
            quantity=1,
            price=1.00,
            tax=1.00,
            metadata="metadata test",
        ),
        ATHM_Item.objects.create(
            name="Second Item",
            transaction=existing_transaction,
            description="This is a description.",
            quantity=1,
            price=1.00,
            tax=1.00,
            metadata="metadata test",
        ),

        existing_transaction.save()

        out = StringIO()
        call_command(
            "athm_sync",
            start=parse_datetime("2020-01-01 12:00:00"),
            end=parse_datetime("2020-01-02 00:00:00"),
            stdout=out,
        )

        assert (
            "Getting transactions from 2020-01-01 12:00:00 to 2020-01-02 00:00:00"
            in out.getvalue()
        )
        assert (
            "Successfully created 1 transactions and updated 1 transactions!"
            in out.getvalue()
        )

        assert ATHM_Transaction.objects.count() == 2
        assert ATHM_Item.objects.count() == 4

        transaction_1 = ATHM_Transaction.objects.get(
            reference_number="212831546-7638e92vjhsbjbsdkjqbjkbqdq"
        )
        assert transaction_1.status == REFUNDED_STATUS
        assert transaction_1.refunded_amount == 1.00
        assert transaction_1.total == 1.00
        assert transaction_1.tax == 1.00
        assert transaction_1.subtotal == 1.00
        assert transaction_1.metadata_1 == "metadata1 test"
        assert transaction_1.metadata_2 == "metadata2 test"

        transaction_2 = ATHM_Transaction.objects.get(
            reference_number="212831546-402894d56b240610016b2e6c78a6003a"
        )
        assert transaction_2.status == COMPLETED_STATUS
        assert transaction_2.total == 5.00
        assert transaction_2.tax == 1.00
        assert transaction_2.subtotal == 4.00

        assert ATHM_Item.objects.filter(
            transaction=transaction_2, name="First Item"
        ).exists()

    def test_command_output_start_date_before_end_date(self):
        out = StringIO()

        with pytest.raises(CommandError) as error:
            call_command(
                "athm_sync",
                start=parse_datetime("2020-01-02 12:00:00"),
                end=parse_datetime("2020-01-01 00:00:00"),
                stdout=out,
            )

        assert "Start date must be before end date!" == str(error.value)

    def test_command_output_missing_public_token(self, settings):
        settings.DJANGO_ATHM_PUBLIC_TOKEN = None

        out = StringIO()

        with pytest.raises(CommandError) as error:
            call_command(
                "athm_sync",
                start=parse_datetime("2020-01-01 12:00:00"),
                end=parse_datetime("2020-01-02 00:00:00"),
                stdout=out,
            )

        assert (
            "Missing public token! Did you forget to set it in your settings?"
            == str(error.value)
        )

    def test_command_output_missing_private_token(self, settings):
        settings.DJANGO_ATHM_PRIVATE_TOKEN = None

        out = StringIO()

        with pytest.raises(CommandError) as error:
            call_command(
                "athm_sync",
                start=parse_datetime("2020-01-01 12:00:00"),
                end=parse_datetime("2020-01-02 00:00:00"),
                stdout=out,
            )

        assert (
            "Missing private token! Did you forget to set it in your settings?"
            == str(error.value)
        )
