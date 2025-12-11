import logging
import uuid
from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone as django_timezone

from django_athm.models import Client, Payment
from django_athm.services.payment_service import PaymentService
from django_athm.utils import normalize_phone_number, safe_decimal

logger = logging.getLogger(__name__)


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
        stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }
        error_details = []

        for txn in ecommerce_completed:
            reference_number = txn.get("referenceNumber")
            if not reference_number:
                stats["errors"] += 1
                error_details.append("Transaction missing referenceNumber")
                continue

            try:
                result = self._process_transaction(txn, dry_run)
                stats[result] += 1
            except Exception as e:
                stats["errors"] += 1
                error_details.append(f"{reference_number}: {e}")
                logger.exception(f"[django-athm] Error processing {reference_number}")

        # Print summary
        self.stdout.write("")
        if dry_run:
            self.stdout.write(f"Would create: {stats['created']} payments")
            self.stdout.write(f"Would update: {stats['updated']} payments")
        else:
            self.stdout.write(f"Created: {stats['created']}")
            self.stdout.write(f"Updated: {stats['updated']}")

        self.stdout.write(f"Skipped: {stats['skipped']}")
        self.stdout.write(f"Errors: {stats['errors']}")

        if error_details:
            self.stdout.write("")
            self.stdout.write("Error details:")
            for detail in error_details[:10]:  # Limit to first 10
                self.stderr.write(f"  - {detail}")
            if len(error_details) > 10:
                self.stderr.write(f"  ... and {len(error_details) - 10} more")

        if stats["errors"] > 0:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Sync completed with errors."))
        else:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Sync completed successfully."))

    def _process_transaction(self, txn: dict, dry_run: bool) -> str:
        """
        Process a single transaction from the report.

        Returns:
            "created", "updated", or "skipped"
        """
        reference_number = txn["referenceNumber"]

        # Try to find existing payment
        payment = Payment.objects.filter(reference_number=reference_number).first()

        if payment:
            return self._update_payment(payment, txn, dry_run)
        else:
            return self._create_payment(txn, dry_run)

    def _update_payment(self, payment: Payment, txn: dict, dry_run: bool) -> str:
        """Update existing payment with remote data if different."""
        changes = self._compute_changes(payment, txn)

        if not changes:
            return "skipped"

        if dry_run:
            return "updated"

        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment.pk)

            # Get or create Client
            client = self._get_or_update_client(
                phone_number=txn.get("phoneNumber"),
                name=txn.get("name", ""),
                email=txn.get("email", ""),
            )

            # Apply changes
            payment.fee = safe_decimal(txn.get("fee"), Decimal("0.00"))
            payment.net_amount = safe_decimal(txn.get("netAmount"), Decimal("0.00"))
            payment.total_refunded_amount = safe_decimal(
                txn.get("totalRefundAmount"), Decimal("0.00")
            )
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

        logger.info(f"[django-athm] Synced payment {payment.reference_number}")
        return "updated"

    def _create_payment(self, txn: dict, dry_run: bool) -> str:
        """Create new payment from remote transaction data."""
        if dry_run:
            return "created"

        reference_number = txn["referenceNumber"]

        with transaction.atomic():
            # Get or create Client
            client = self._get_or_update_client(
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
                    total=safe_decimal(txn.get("total"), Decimal("0.00")),
                    subtotal=safe_decimal(txn.get("subtotal"), Decimal("0.00")),
                    tax=safe_decimal(txn.get("tax"), Decimal("0.00")),
                    fee=safe_decimal(txn.get("fee"), Decimal("0.00")),
                    net_amount=safe_decimal(txn.get("netAmount"), Decimal("0.00")),
                    total_refunded_amount=safe_decimal(
                        txn.get("totalRefundAmount"), Decimal("0.00")
                    ),
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

        logger.info(f"[django-athm] Created payment from sync: {reference_number}")
        return "created"

    def _compute_changes(self, payment: Payment, txn: dict) -> dict:
        """
        Compute differences between local payment and remote transaction.

        Returns dict of field_name -> (local_value, remote_value) for changed fields.
        """
        changes = {}

        # Compare financial fields
        remote_fee = safe_decimal(txn.get("fee"), Decimal("0.00"))
        if payment.fee != remote_fee:
            changes["fee"] = (payment.fee, remote_fee)

        remote_net = safe_decimal(txn.get("netAmount"), Decimal("0.00"))
        if payment.net_amount != remote_net:
            changes["net_amount"] = (payment.net_amount, remote_net)

        remote_refunded = safe_decimal(txn.get("totalRefundAmount"), Decimal("0.00"))
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

    def _get_or_update_client(
        self, phone_number: str | None, name: str = "", email: str = ""
    ) -> Client | None:
        """
        Get or create Client record by normalized phone number.
        Updates name/email with latest information (latest wins).
        """
        if not phone_number:
            return None

        normalized_phone = normalize_phone_number(phone_number)
        if not normalized_phone:
            return None

        client, created = Client.objects.get_or_create(
            phone_number=normalized_phone,
            defaults={"name": name or "", "email": email or ""},
        )

        if not created:
            updated = False
            if name and client.name != name:
                client.name = name
                updated = True
            if email and client.email != email:
                client.email = email
                updated = True

            if updated:
                client.save(update_fields=["name", "email", "modified"])

        return client

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

        logger.warning(f"[django-athm] Could not parse transaction date: {date_str}")
        return None
