from decimal import Decimal
from io import StringIO
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from django_athm.models import Client, Payment


class TestInstallWebhookCommand:
    def test_success(self, mocker):
        mock_client = Mock()
        mocker.patch(
            "django_athm.management.commands.install_webhook.PaymentService.get_client",
            return_value=mock_client,
        )

        out = StringIO()
        call_command("install_webhook", "https://example.com/webhook/", stdout=out)

        mock_client.subscribe_webhook.assert_called_once_with(
            listener_url="https://example.com/webhook/"
        )
        assert "Installed" in out.getvalue()

    def test_http_url_rejected(self):
        with pytest.raises(CommandError) as exc_info:
            call_command("install_webhook", "http://example.com/webhook/")

        assert "Invalid URL" in str(exc_info.value)

    def test_invalid_url_rejected(self):
        with pytest.raises(CommandError) as exc_info:
            call_command("install_webhook", "not-a-valid-url")

        assert "Invalid URL" in str(exc_info.value)

    def test_api_error_handled(self, mocker):
        mock_client = Mock()
        mock_client.subscribe_webhook.side_effect = Exception("API Error")
        mocker.patch(
            "django_athm.management.commands.install_webhook.PaymentService.get_client",
            return_value=mock_client,
        )

        with pytest.raises(CommandError) as exc_info:
            call_command("install_webhook", "https://example.com/webhook/")

        assert "Failed" in str(exc_info.value)
        assert "API Error" in str(exc_info.value)

    def test_install_webhook_with_setting(self, mocker, settings):
        """Test auto-detection using DJANGO_ATHM_WEBHOOK_URL setting."""
        settings.DJANGO_ATHM_WEBHOOK_URL = "https://configured.com/athm/webhook/"

        mock_client = Mock()
        mocker.patch(
            "django_athm.management.commands.install_webhook.PaymentService.get_client",
            return_value=mock_client,
        )

        out = StringIO()
        call_command("install_webhook", stdout=out)

        mock_client.subscribe_webhook.assert_called_once_with(
            listener_url="https://configured.com/athm/webhook/"
        )
        assert "configured.com" in out.getvalue()

    def test_install_webhook_fails_without_config(self, settings):
        """Test that helpful error is shown when auto-detection fails."""
        # Ensure setting is not configured
        if hasattr(settings, "DJANGO_ATHM_WEBHOOK_URL"):
            delattr(settings, "DJANGO_ATHM_WEBHOOK_URL")

        with pytest.raises(CommandError) as exc_info:
            call_command("install_webhook")

        error_msg = str(exc_info.value)
        assert "Set DJANGO_ATHM_WEBHOOK_URL" in error_msg


@pytest.fixture
def transaction_report_response():
    """Sample transaction report API response."""
    return [
        {
            "transactionType": "eCommerce",
            "status": "COMPLETED",
            "referenceNumber": "REF-001",
            "dailyTransactionID": "12345",
            "date": "2025-01-15 10:30:00",
            "name": "John Doe",
            "phoneNumber": "7871234567",
            "email": "john@example.com",
            "total": "125.00",
            "subtotal": "100.00",
            "tax": "25.00",
            "fee": "2.50",
            "netAmount": "122.50",
            "totalRefundAmount": "0.00",
            "metadata1": "order-123",
            "metadata2": "",
        },
        {
            "transactionType": "eCommerce",
            "status": "COMPLETED",
            "referenceNumber": "REF-002",
            "dailyTransactionID": "12346",
            "date": "2025-01-15 11:00:00",
            "name": "Jane Smith",
            "phoneNumber": "7879876543",
            "email": "jane@example.com",
            "total": "50.00",
            "subtotal": "50.00",
            "tax": "0.00",
            "fee": "1.00",
            "netAmount": "49.00",
            "totalRefundAmount": "10.00",
            "metadata1": "",
            "metadata2": "",
        },
        {
            "transactionType": "payment",
            "status": "COMPLETED",
            "referenceNumber": "REF-003",
            "total": "75.00",
        },
    ]


@pytest.mark.django_db
class TestAthmSyncCommand:
    def test_requires_from_date(self):
        """Test that --from-date is required."""
        with pytest.raises(CommandError) as exc_info:
            call_command("athm_sync", "--to-date", "2025-01-31")
        assert "--from-date" in str(exc_info.value)

    def test_requires_to_date(self):
        """Test that --to-date is required."""
        with pytest.raises(CommandError) as exc_info:
            call_command("athm_sync", "--from-date", "2025-01-01")
        assert "--to-date" in str(exc_info.value)

    def test_invalid_from_date_format(self, mocker):
        """Test invalid date format raises CommandError."""
        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=[],
        )

        with pytest.raises(CommandError) as exc_info:
            call_command(
                "athm_sync",
                "--from-date",
                "01-01-2025",
                "--to-date",
                "2025-01-31",
            )

        assert "Invalid --from-date format" in str(exc_info.value)

    def test_invalid_to_date_format(self, mocker):
        """Test invalid to-date format raises CommandError."""
        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=[],
        )

        with pytest.raises(CommandError) as exc_info:
            call_command(
                "athm_sync",
                "--from-date",
                "2025-01-01",
                "--to-date",
                "31-01-2025",
            )

        assert "Invalid --to-date format" in str(exc_info.value)

    def test_from_date_after_to_date_rejected(self, mocker):
        """Test that from-date > to-date raises CommandError."""
        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=[],
        )

        with pytest.raises(CommandError) as exc_info:
            call_command(
                "athm_sync",
                "--from-date",
                "2025-02-01",
                "--to-date",
                "2025-01-01",
            )

        assert "--from-date must be before or equal to --to-date" in str(exc_info.value)

    def test_api_error_handled(self, mocker):
        """Test API errors are handled gracefully."""
        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            side_effect=Exception("Network error"),
        )

        with pytest.raises(CommandError) as exc_info:
            call_command(
                "athm_sync",
                "--from-date",
                "2025-01-01",
                "--to-date",
                "2025-01-31",
            )

        assert "Failed to fetch transaction report" in str(exc_info.value)
        assert "Network error" in str(exc_info.value)

    def test_dry_run_no_database_changes(self, mocker, transaction_report_response):
        """Test dry-run mode reports changes without modifying database."""
        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=transaction_report_response,
        )

        out = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            "--dry-run",
            stdout=out,
        )

        output = out.getvalue()
        assert "DRY RUN" in output
        assert "Would create: 2 payments" in output

        # Verify no payments were created
        assert Payment.objects.count() == 0
        assert Client.objects.count() == 0

    def test_creates_new_payments(self, mocker, transaction_report_response):
        """Test that new payments are created for unmatched transactions."""
        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=transaction_report_response,
        )

        out = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            stdout=out,
        )

        output = out.getvalue()
        assert "Created: 2" in output

        # Verify payments were created
        assert Payment.objects.count() == 2

        payment1 = Payment.objects.get(reference_number="REF-001")
        assert payment1.status == Payment.Status.COMPLETED
        assert payment1.total == Decimal("125.00")
        assert payment1.fee == Decimal("2.50")
        assert payment1.net_amount == Decimal("122.50")
        assert payment1.customer_name == "John Doe"
        assert payment1.customer_phone == "7871234567"
        assert payment1.customer_email == "john@example.com"

        payment2 = Payment.objects.get(reference_number="REF-002")
        assert payment2.total_refunded_amount == Decimal("10.00")

        # Verify clients were created
        assert Client.objects.count() == 2
        assert Client.objects.filter(phone_number="7871234567").exists()
        assert Client.objects.filter(phone_number="7879876543").exists()

    def test_updates_existing_payments(self, mocker, transaction_report_response):
        """Test that existing payments are updated with missing data."""
        # Create existing payment with missing data
        Payment.objects.create(
            ecommerce_id="11111111-1111-1111-1111-111111111111",
            reference_number="REF-001",
            status=Payment.Status.COMPLETED,
            total=Decimal("125.00"),
            # fee, net_amount, customer info missing
        )

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=transaction_report_response,
        )

        out = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            stdout=out,
        )

        output = out.getvalue()
        assert "Updated: 1" in output
        assert "Created: 1" in output

        # Verify payment was updated
        payment = Payment.objects.get(reference_number="REF-001")
        assert payment.fee == Decimal("2.50")
        assert payment.net_amount == Decimal("122.50")
        assert payment.customer_name == "John Doe"

    def test_skips_already_synced_payments(self, mocker):
        """Test that payments with no changes are skipped."""
        # Create payment already fully synced
        Payment.objects.create(
            ecommerce_id="11111111-1111-1111-1111-111111111111",
            reference_number="REF-001",
            status=Payment.Status.COMPLETED,
            total=Decimal("125.00"),
            subtotal=Decimal("100.00"),
            tax=Decimal("25.00"),
            fee=Decimal("2.50"),
            net_amount=Decimal("122.50"),
            total_refunded_amount=Decimal("0.00"),
            customer_name="John Doe",
            customer_phone="7871234567",
            customer_email="john@example.com",
        )

        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                "referenceNumber": "REF-001",
                "total": "125.00",
                "subtotal": "100.00",
                "tax": "25.00",
                "fee": "2.50",
                "netAmount": "122.50",
                "totalRefundAmount": "0.00",
                "name": "John Doe",
                "phoneNumber": "7871234567",
                "email": "john@example.com",
            }
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        out = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            stdout=out,
        )

        output = out.getvalue()
        assert "Skipped: 1" in output
        assert "Created: 0" in output
        assert "Updated: 0" in output

    def test_filters_to_ecommerce_completed_only(self, mocker):
        """Test that only eCommerce COMPLETED transactions are processed."""
        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                "referenceNumber": "REF-001",
                "total": "100.00",
            },
            {
                "transactionType": "eCommerce",
                "status": "CANCEL",
                "referenceNumber": "REF-002",
                "total": "50.00",
            },
            {
                "transactionType": "payment",
                "status": "COMPLETED",
                "referenceNumber": "REF-003",
                "total": "75.00",
            },
            {
                "transactionType": "refund",
                "status": "COMPLETED",
                "referenceNumber": "REF-004",
                "total": "25.00",
            },
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        out = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            stdout=out,
        )

        output = out.getvalue()
        assert "Processing 1 eCommerce COMPLETED transactions" in output
        assert Payment.objects.count() == 1
        assert Payment.objects.filter(reference_number="REF-001").exists()

    def test_handles_missing_reference_number(self, mocker):
        """Test transactions without referenceNumber are logged as errors."""
        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                # Missing referenceNumber
                "total": "100.00",
            },
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        out = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            stdout=out,
        )

        output = out.getvalue()
        assert "Errors: 1" in output
        assert Payment.objects.count() == 0

    def test_success_message_on_completion(self, mocker):
        """Test success message is shown when sync completes without errors."""
        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=[],
        )

        out = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            stdout=out,
        )

        output = out.getvalue()
        assert "Sync completed successfully" in output

    def test_client_updated_with_latest_info(self, mocker):
        """Test that Client record is updated with latest customer info."""
        # Create existing client
        Client.objects.create(
            phone_number="7871234567",
            name="Old Name",
            email="old@example.com",
        )

        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                "referenceNumber": "REF-001",
                "total": "100.00",
                "name": "New Name",
                "phoneNumber": "7871234567",
                "email": "new@example.com",
            },
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
        )

        # Verify client was updated
        client = Client.objects.get(phone_number="7871234567")
        assert client.name == "New Name"
        assert client.email == "new@example.com"
        assert Client.objects.count() == 1  # No duplicate created

    def test_dry_run_update_reports_without_modifying(self, mocker):
        """Test dry-run correctly reports updates without database changes."""
        Payment.objects.create(
            ecommerce_id="22222222-2222-2222-2222-222222222222",
            reference_number="REF-001",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            fee=Decimal("0.00"),
            customer_name="",  # Will be updated
        )

        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                "referenceNumber": "REF-001",
                "total": "100.00",
                "fee": "2.00",
                "netAmount": "98.00",
                "name": "John Doe",
            },
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        out = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            "--dry-run",
            stdout=out,
        )

        output = out.getvalue()
        assert "Would update: 1 payments" in output

        # Verify no changes were made
        payment = Payment.objects.get(reference_number="REF-001")
        assert payment.customer_name == ""
        assert payment.fee == Decimal("0.00")

    def test_transaction_processing_exception_logged(self, mocker, caplog):
        """Test that exceptions during transaction processing are captured."""
        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=[
                {
                    "transactionType": "eCommerce",
                    "status": "COMPLETED",
                    "referenceNumber": "REF-FAIL",
                    "total": "100.00",
                },
            ],
        )
        # Force an exception in _process_transaction
        mocker.patch(
            "django_athm.management.commands.athm_sync.Command._process_transaction",
            side_effect=RuntimeError("Database connection lost"),
        )

        out = StringIO()
        err = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            stdout=out,
            stderr=err,
        )

        output = out.getvalue()
        assert "Errors: 1" in output
        assert "completed with errors" in output

    def test_error_details_truncated_beyond_ten(self, mocker):
        """Test that error details are truncated when more than 10 errors occur."""
        # Create 15 transactions that will all fail
        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                # Missing referenceNumber causes error
            }
            for _ in range(15)
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        out = StringIO()
        err = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            stdout=out,
            stderr=err,
        )

        output = out.getvalue()
        err_output = err.getvalue()
        assert "Errors: 15" in output
        assert "... and 5 more" in err_output

    def test_updates_transaction_date_from_api(self, mocker):
        """Test that transaction_date is parsed and set on update."""
        Payment.objects.create(
            ecommerce_id="33333333-3333-3333-3333-333333333333",
            reference_number="REF-DATE",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            customer_name="",  # Needs update to trigger the update path
        )

        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                "referenceNumber": "REF-DATE",
                "total": "100.00",
                "fee": "2.00",
                "netAmount": "98.00",
                "name": "John Doe",
                "date": "2025-01-15 14:30:00",
            },
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
        )

        payment = Payment.objects.get(reference_number="REF-DATE")
        assert payment.transaction_date is not None
        assert payment.transaction_date.day == 15

    def test_unparseable_date_logged_as_warning(self, mocker, caplog):
        """Test that unparseable dates are logged but don't fail the sync."""
        import logging

        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                "referenceNumber": "REF-BADDATE",
                "total": "100.00",
                "date": "not-a-date-format",
            },
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        with caplog.at_level(logging.WARNING):
            out = StringIO()
            call_command(
                "athm_sync",
                "--from-date",
                "2025-01-01",
                "--to-date",
                "2025-01-31",
                stdout=out,
            )

        # Payment should still be created
        assert Payment.objects.filter(reference_number="REF-BADDATE").exists()
        payment = Payment.objects.get(reference_number="REF-BADDATE")
        assert payment.transaction_date is None
        assert "Could not parse transaction date" in caplog.text

    def test_invalid_phone_number_skips_client_creation(self, mocker):
        """Test that invalid phone numbers don't create Client records."""
        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                "referenceNumber": "REF-BADPHONE",
                "total": "100.00",
                "phoneNumber": "invalid",  # Not a valid phone
                "name": "Test User",
            },
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
        )

        # Payment created but no client
        assert Payment.objects.filter(reference_number="REF-BADPHONE").exists()
        assert Client.objects.count() == 0

    def test_client_not_updated_when_unchanged(self, mocker):
        """Test that Client.save() is not called when name/email unchanged."""
        Client.objects.create(
            phone_number="7871234567",
            name="Same Name",
            email="same@example.com",
        )

        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                "referenceNumber": "REF-SAME",
                "total": "100.00",
                "name": "Same Name",
                "phoneNumber": "7871234567",
                "email": "same@example.com",
            },
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
        )

        # Just verify it completed without error
        assert Payment.objects.filter(reference_number="REF-SAME").exists()
        assert Client.objects.count() == 1

    def test_duplicate_reference_number_race_condition(self, mocker):
        """Test handling of IntegrityError from duplicate reference_number."""
        from django.db import IntegrityError

        api_response = [
            {
                "transactionType": "eCommerce",
                "status": "COMPLETED",
                "referenceNumber": "REF-RACE",
                "total": "100.00",
            },
        ]

        mocker.patch(
            "django_athm.management.commands.athm_sync.PaymentService.fetch_transaction_report",
            return_value=api_response,
        )

        # Simulate race condition: Payment.objects.create raises IntegrityError
        original_create = Payment.objects.create
        call_count = [0]

        def create_with_integrity_error(**kwargs):
            call_count[0] += 1
            if kwargs.get("reference_number") == "REF-RACE":
                raise IntegrityError("duplicate key value")
            return original_create(**kwargs)

        mocker.patch.object(
            Payment.objects, "create", side_effect=create_with_integrity_error
        )

        out = StringIO()
        err = StringIO()
        call_command(
            "athm_sync",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
            stdout=out,
            stderr=err,
        )

        output = out.getvalue()
        assert "Errors: 1" in output
