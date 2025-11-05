from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from django_athm.constants import TransactionStatus
from django_athm.management.commands.athm_sync import get_status
from django_athm.models import ATHM_Client, ATHM_Item, ATHM_Transaction


class TestSyncCommand:
    def test_get_status_refund_success(self):
        upstream_transaction = {
            "transactionType": "REFUND",
            "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
            "date": "2019-06-06 17:12:02.0",
            "totalRefundAmount": "1.00",
            "total": "1.00",
            "tax": "1.00",
            "subtotal": "1.00",
            "metadata1": "metadata1 test",
            "metadata2": "metadata2 test",
            "items": [],
        }

        status = get_status(upstream_transaction)
        assert status == ATHM_Transaction.Status.REFUNDED

    def test_get_status_ecommerce_refund_success(self):
        upstream_transaction = {
            "transactionType": "ECOMMERCE",
            "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
            "date": "2019-06-06 17:12:02.0",
            "totalRefundAmount": "1.00",
            "total": "1.00",
            "tax": "1.00",
            "subtotal": "1.00",
            "metadata1": "metadata1 test",
            "metadata2": "metadata2 test",
            "items": [],
        }

        status = get_status(upstream_transaction)
        assert status == ATHM_Transaction.Status.REFUNDED

    def test_get_status_ecommerce_non_refund_success(self):
        upstream_transaction = {
            "transactionType": "ECOMMERCE",
            "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
            "date": "2019-06-06 17:12:02.0",
            "totalRefundAmount": "0.00",
            "total": "1.00",
            "tax": "1.00",
            "subtotal": "1.00",
            "metadata1": "metadata1 test",
            "metadata2": "metadata2 test",
            "items": [],
        }

        status = get_status(upstream_transaction)
        assert status == ATHM_Transaction.Status.COMPLETED

    def test_get_status_other(self):
        upstream_transaction = {
            "status": TransactionStatus.expired.value,
            "transactionType": TransactionStatus.expired.value,
            "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
            "date": "2019-06-06 17:12:02.0",
            "totalRefundAmount": "1.00",
            "total": "1.00",
            "tax": "1.00",
            "subtotal": "1.00",
            "metadata1": "metadata1 test",
            "metadata2": "metadata2 test",
            "items": [],
        }

        status = get_status(upstream_transaction)
        assert status == TransactionStatus.expired.value

    @pytest.mark.django_db
    def test_command_output_success(self, mock_http_adapter_get_with_data):
        mock_http_adapter_get_with_data.return_value = [
            {
                "transactionType": "REFUND",
                "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
                "date": "2019-06-06 17:12:02.0",
                "name": "Tester Test",
                "phoneNumber": "(787) 123-4567",
                "email": "tester@django-athm.com",
                "total": "1.00",
                "totalRefundAmount": "1.00",
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
                "transactionType": "ECOMMERCE",
                "status": "COMPLETED",
                "referenceNumber": "212831546-402894d56b240610016b2e6c78a6003a",
                "date": "2019-06-06 16:12:02.0",
                "name": "Tester Test",
                "phoneNumber": "(787) 123-4567",
                "email": "tester@django-athm.com",
                "total": "5.00",
                "totalRefundAmount": "5.00",
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
            status=ATHM_Transaction.Status.COMPLETED,
            reference_number="212831546-402894d56b240610016b2e6c78a6003a",
            date=make_aware(parse_datetime("2019-06-06 16:12:02.0")),
            refunded_amount=0.00,
            total=5.00,
            tax=1.00,
            subtotal=4.00,
            metadata_1="metadata1 test",
            metadata_2="metadata2 test",
        )

        (
            ATHM_Item.objects.create(
                name="First Item",
                transaction=existing_transaction,
                description="This is a description.",
                quantity=1,
                price=1.00,
                tax=1.00,
                metadata="metadata test",
            ),
        )
        (
            ATHM_Item.objects.create(
                name="Second Item",
                transaction=existing_transaction,
                description="This is a description.",
                quantity=1,
                price=1.00,
                tax=1.00,
                metadata="metadata test",
            ),
        )

        existing_transaction.save()

        out = StringIO()
        call_command(
            "athm_sync",
            start=parse_datetime("2020-01-01 12:00:00"),
            end=parse_datetime("2020-01-02 00:00:00"),
            stdout=out,
        )

        output = out.getvalue()
        assert (
            "Getting transactions from 2020-01-01 12:00:00 to 2020-01-02 00:00:00"
            in output
        )
        assert (
            "Successfully created 1 transaction(s), updated 1 transaction(s), and created 1 client(s)!"
            in output
        )

        assert ATHM_Transaction.objects.count() == 2
        assert ATHM_Item.objects.count() == 6
        assert ATHM_Client.objects.count() == 1

        transaction_1 = ATHM_Transaction.objects.get(
            reference_number="212831546-7638e92vjhsbjbsdkjqbjkbqdq"
        )
        assert transaction_1.status == ATHM_Transaction.Status.REFUNDED
        assert transaction_1.refunded_amount == 1.00
        assert transaction_1.total == 1.00
        assert transaction_1.tax == 1.00
        assert transaction_1.subtotal == 1.00
        assert transaction_1.metadata_1 == "metadata1 test"
        assert transaction_1.metadata_2 == "metadata2 test"

        transaction_2 = ATHM_Transaction.objects.get(
            reference_number="212831546-402894d56b240610016b2e6c78a6003a"
        )
        assert transaction_2.status == ATHM_Transaction.Status.REFUNDED
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

        assert str(error.value) == "Start date must be before end date!"

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
            str(error.value)
            == "Missing public token! Did you forget to set it in your settings?"
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
            str(error.value)
            == "Missing private token! Did you forget to set it in your settings?"
        )
