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
