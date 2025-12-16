import logging
import uuid
from datetime import datetime
from enum import Enum

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone as django_timezone

from django_athm.models import Payment
from django_athm.services import ClientService, PaymentService
from django_athm.utils import safe_decimal

__all__ = ["Command", "SyncResult"]

logger = logging.getLogger(__name__)


class SyncResult(str, Enum):
    """Result of syncing a single transaction."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    ERROR = "errors"


class Command(BaseCommand):
    help = "Reconcile local Payment records with ATH Movil Transaction Report API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-date",
            required=True,
            type=str,
            help="Start date for report (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--to-date",
            required=True,
            type=str,
            help="End date for report (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without modifying database",
        )

    def handle(self, *args, **options):
        from_date_str = options["from_date"]
        to_date_str = options["to_date"]
        dry_run = options["dry_run"]

        # Validate and convert dates
        try:
            from_date = datetime.strptime(from_date_str, "%Y-%m-%d")
        except ValueError as e:
            raise CommandError(
                f"Invalid --from-date format. Use YYYY-MM-DD. Error: {e}"
            ) from e

        try:
            to_date = datetime.strptime(to_date_str, "%Y-%m-%d")
        except ValueError as e:
            raise CommandError(
                f"Invalid --to-date format. Use YYYY-MM-DD. Error: {e}"
            ) from e

        if from_date > to_date:
            raise CommandError("--from-date must be before or equal to --to-date")

        # Convert to API format
        api_from_date = from_date.strftime("%Y-%m-%d 00:00:00")
        api_to_date = to_date.strftime("%Y-%m-%d 23:59:59")

        # Print header
        mode = "(DRY RUN)" if dry_run else ""
        self.stdout.write(f"ATH Movil Sync {mode}")
        self.stdout.write("=" * 40)
        self.stdout.write(f"Date range: {from_date_str} to {to_date_str}")

        # Fetch transactions
        try:
            transactions = PaymentService.fetch_transaction_report(
                from_date=api_from_date,
                to_date=api_to_date,
            )
        except Exception as e:
            raise CommandError(f"Failed to fetch transaction report: {e}") from e

        self.stdout.write(f"Fetched {len(transactions)} transactions")
        self.stdout.write("")

        # Filter to eCommerce COMPLETED only
        ecommerce_completed = [
            txn
            for txn in transactions
            if txn.get("transactionType") == "eCommerce"
            and txn.get("status") == "COMPLETED"
        ]

        self.stdout.write(
            f"Processing {len(ecommerce_completed)} eCommerce COMPLETED transactions"
        )

        # Track stats
        stats = dict.fromkeys(SyncResult, 0)
        error_details = []

        for txn in ecommerce_completed:
            reference_number = txn.get("referenceNumber")
            if not reference_number:
                stats[SyncResult.ERROR] += 1
                error_details.append("Transaction missing referenceNumber")
                continue

            try:
                result = self._process_transaction(txn, dry_run)
                stats[result] += 1
            except Exception as e:
                stats[SyncResult.ERROR] += 1
                error_details.append(f"{reference_number}: {e}")
                logger.exception("[django-athm] Error processing %s", reference_number)

        # Print summary
        self.stdout.write("")
        if dry_run:
            self.stdout.write(f"Would create: {stats[SyncResult.CREATED]} payments")
            self.stdout.write(f"Would update: {stats[SyncResult.UPDATED]} payments")
        else:
            self.stdout.write(f"Created: {stats[SyncResult.CREATED]}")
            self.stdout.write(f"Updated: {stats[SyncResult.UPDATED]}")

        self.stdout.write(f"Skipped: {stats[SyncResult.SKIPPED]}")
        self.stdout.write(f"Errors: {stats[SyncResult.ERROR]}")

        if error_details:
            self.stdout.write("")
            self.stdout.write("Error details:")
            for detail in error_details[:10]:  # Limit to first 10
                self.stderr.write(f"  - {detail}")
            if len(error_details) > 10:
                self.stderr.write(f"  ... and {len(error_details) - 10} more")

        if stats[SyncResult.ERROR] > 0:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Sync completed with errors."))
        else:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Sync completed successfully."))

    def _process_transaction(self, txn: dict, dry_run: bool) -> SyncResult:
        """
        Process a single transaction from the report.

        Returns:
            SyncResult indicating what happened
        """
        reference_number = txn["referenceNumber"]

        # Try to find existing payment
        payment = Payment.objects.filter(reference_number=reference_number).first()

        if payment:
            return self._update_payment(payment, txn, dry_run)
        else:
            return self._create_payment(txn, dry_run)

    def _update_payment(self, payment: Payment, txn: dict, dry_run: bool) -> SyncResult:
        """Update existing payment with remote data if different."""
        changes = self._compute_changes(payment, txn)

        if not changes:
            return SyncResult.SKIPPED

        if dry_run:
            return SyncResult.UPDATED

        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment.pk)

            # Get or create Client
            client = ClientService.get_or_update(
                phone_number=txn.get("phoneNumber"),
                name=txn.get("name", ""),
                email=txn.get("email", ""),
            )

            # Apply changes
            payment.fee = safe_decimal(txn.get("fee"))
            payment.net_amount = safe_decimal(txn.get("netAmount"))
            payment.total_refunded_amount = safe_decimal(txn.get("totalRefundAmount"))
            payment.daily_transaction_id = txn.get("dailyTransactionID", "")
            payment.customer_name = txn.get("name", "")
            payment.customer_phone = txn.get("phoneNumber", "")
            payment.customer_email = txn.get("email", "")
            payment.client = client

            # Parse and set transaction_date
            txn_date = txn.get("date")
            if txn_date:
                parsed_date = self._parse_transaction_date(txn_date)
                if parsed_date:
                    payment.transaction_date = parsed_date

            payment.save()

        logger.info("[django-athm] Synced payment %s", payment.reference_number)
        return SyncResult.UPDATED

    def _create_payment(self, txn: dict, dry_run: bool) -> SyncResult:
        """Create new payment from remote transaction data."""
        if dry_run:
            return SyncResult.CREATED

        reference_number = txn["referenceNumber"]

        with transaction.atomic():
            # Get or create Client
            client = ClientService.get_or_update(
                phone_number=txn.get("phoneNumber"),
                name=txn.get("name", ""),
                email=txn.get("email", ""),
            )

            # Parse transaction date
            txn_date = txn.get("date")
            transaction_date = None
            if txn_date:
                transaction_date = self._parse_transaction_date(txn_date)

            try:
                Payment.objects.create(
                    ecommerce_id=uuid.uuid4(),
                    reference_number=reference_number,
                    daily_transaction_id=txn.get("dailyTransactionID", ""),
                    status=Payment.Status.COMPLETED,
                    total=safe_decimal(txn.get("total")),
                    subtotal=safe_decimal(txn.get("subtotal")),
                    tax=safe_decimal(txn.get("tax")),
                    fee=safe_decimal(txn.get("fee")),
                    net_amount=safe_decimal(txn.get("netAmount")),
                    total_refunded_amount=safe_decimal(txn.get("totalRefundAmount")),
                    customer_name=txn.get("name", ""),
                    customer_phone=txn.get("phoneNumber", ""),
                    customer_email=txn.get("email", ""),
                    metadata_1=txn.get("metadata1", ""),
                    metadata_2=txn.get("metadata2", ""),
                    client=client,
                    transaction_date=transaction_date,
                )
            except IntegrityError as e:
                # Duplicate reference_number (race condition)
                raise ValueError(
                    f"Duplicate reference_number: {reference_number}"
                ) from e

        logger.info("[django-athm] Created payment from sync: %s", reference_number)
        return SyncResult.CREATED

    def _compute_changes(self, payment: Payment, txn: dict) -> dict:
        """
        Compute differences between local payment and remote transaction.

        Returns dict of field_name -> (local_value, remote_value) for changed fields.
        """
        changes = {}

        # Compare financial fields
        remote_fee = safe_decimal(txn.get("fee"))
        if payment.fee != remote_fee:
            changes["fee"] = (payment.fee, remote_fee)

        remote_net = safe_decimal(txn.get("netAmount"))
        if payment.net_amount != remote_net:
            changes["net_amount"] = (payment.net_amount, remote_net)

        remote_refunded = safe_decimal(txn.get("totalRefundAmount"))
        if payment.total_refunded_amount != remote_refunded:
            changes["total_refunded_amount"] = (
                payment.total_refunded_amount,
                remote_refunded,
            )

        # Compare customer fields
        remote_name = txn.get("name", "")
        if payment.customer_name != remote_name:
            changes["customer_name"] = (payment.customer_name, remote_name)

        remote_phone = txn.get("phoneNumber", "")
        if payment.customer_phone != remote_phone:
            changes["customer_phone"] = (payment.customer_phone, remote_phone)

        remote_email = txn.get("email", "")
        if payment.customer_email != remote_email:
            changes["customer_email"] = (payment.customer_email, remote_email)

        return changes

    def _parse_transaction_date(self, date_str: str):
        """Parse transaction date from API response."""
        if not date_str:
            return None

        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Make timezone-aware
                if dt.tzinfo is None:
                    dt = django_timezone.make_aware(dt)
                return dt
            except ValueError:
                continue

        logger.warning("[django-athm] Could not parse transaction date: %s", date_str)
        return None
