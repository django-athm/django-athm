from decimal import Decimal

import phonenumbers
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from django_athm.conf import settings as app_settings
from django_athm.constants import TransactionType
from django_athm.models import ATHM_Client, ATHM_Item, ATHM_Transaction


def _safe_decimal(value, default=None):
    """Safely convert value to Decimal."""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return default


def get_status(transaction):
    """
    Determine transaction status from API data.

    The transactionReport API returns transactions with transactionType and status.
    We map these to our internal Status choices.
    """
    transaction_type = transaction.get("transactionType", "").upper()

    # Handle refund transactions
    if transaction_type == TransactionType.refund.value:
        return ATHM_Transaction.Status.REFUNDED

    # Handle ecommerce transactions
    elif transaction_type == TransactionType.ecommerce.value:
        refund_amount = _safe_decimal(transaction.get("totalRefundAmount", 0), Decimal("0"))
        if refund_amount > 0:
            return ATHM_Transaction.Status.REFUNDED
        else:
            return ATHM_Transaction.Status.COMPLETED

    # For other cases, try to map the status or transactionType to our Status choices
    # This handles edge cases where transactionType might be a status value
    status_value = transaction.get("status", transaction_type).upper()

    # Map common status values
    status_mapping = {
        "COMPLETED": ATHM_Transaction.Status.COMPLETED,
        "REFUNDED": ATHM_Transaction.Status.REFUNDED,
        "EXPIRED": ATHM_Transaction.Status.EXPIRED,
        "CANCELLED": ATHM_Transaction.Status.CANCELLED,
        "CANCEL": ATHM_Transaction.Status.CANCEL,
        "OPEN": ATHM_Transaction.Status.OPEN,
        "CONFIRM": ATHM_Transaction.Status.CONFIRM,
    }

    return status_mapping.get(status_value, ATHM_Transaction.Status.COMPLETED)


def get_defaults(transaction):
    """Extract transaction fields for update_or_create."""
    return dict(
        reference_number=transaction["referenceNumber"],
        status=get_status(transaction),
        date=make_aware(parse_datetime(transaction["date"])),
        total=_safe_decimal(transaction.get("total"), Decimal("0")),
        tax=_safe_decimal(transaction.get("tax")),
        refunded_amount=_safe_decimal(transaction.get("totalRefundAmount")),
        subtotal=_safe_decimal(transaction.get("subtotal")),
        fee=_safe_decimal(transaction.get("fee")),
        metadata_1=transaction.get("metadata1"),
        metadata_2=transaction.get("metadata2"),
        customer_name=transaction.get("name", ""),
        customer_phone=transaction.get("phoneNumber", ""),
        business_name=transaction.get("businessName", ""),
    )


class Command(BaseCommand):
    help = "Synchronize the database with results from the ATH Móvil API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--start",
            type=parse_datetime,
            required=True,
            help='Start datetime for transactions sync. Format = "2020-01-01 16:05:54"',
            metavar="START_DATE",
        )

        parser.add_argument(
            "--end",
            type=parse_datetime,
            required=True,
            help='End datetime for transactions sync. Format = "2020-02-03 18:25:00"',
            metavar="END_DATE",
        )

        parser.add_argument(
            "--public-token",
            type=str,
            required=False,
            default=app_settings.PUBLIC_TOKEN,
            help="Your ATH Móvil Business public token. Default = settings.DJANGO_ATHM_PUBLIC_TOKEN",
            metavar="ATHM_PUBLIC_TOKEN",
        )

        parser.add_argument(
            "--private-token",
            type=str,
            required=False,
            default=app_settings.PRIVATE_TOKEN,
            help="Your ATH Móvil Business private token. Default = settings.DJANGO_ATHM_PRIVATE_TOKEN",
            metavar="ATHM_PRIVATE_TOKEN",
        )

    def handle(self, *args, **options):
        public_token = options["public_token"]
        private_token = options["private_token"]

        if not public_token:
            raise CommandError(
                "Missing public token! Did you forget to set it in your settings?"
            )

        if not private_token:
            raise CommandError(
                "Missing private token! Did you forget to set it in your settings?"
            )

        start_date = options["start"]
        end_date = options["end"]

        # Check to make sure that start_date is before end_date
        difference = end_date - start_date

        if difference.days < 0:
            raise CommandError("Start date must be before end date!")

        self.stdout.write(f"Getting transactions from {start_date} to {end_date}...")

        # Call the ATH Móvil API and get all transactions between the selected dates
        report_data = ATHM_Transaction.get_report(
            start_date=str(start_date),
            end_date=str(end_date),
            public_token=public_token,
            private_token=private_token,
        )

        if "errorMessage" in report_data:
            error_details = report_data["errorMessage"]
            raise CommandError(error_details)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully obtained {len(report_data)} transactions!"
            )
        )

        # Check which transactions are already in the database
        total_transaction_created = 0
        total_transactions_updated = 0

        total_clients_created = 0

        self.stdout.write("Saving results to database...")

        # For each transaction, create or update an ATHM_Transaction instance
        for transaction_data in report_data:
            (
                transaction,
                transaction_created,
            ) = ATHM_Transaction.objects.update_or_create(
                reference_number=transaction_data["referenceNumber"],
                defaults=get_defaults(transaction_data),
            )

            phone_number_parsed = phonenumbers.parse(
                transaction_data["phoneNumber"], "US"
            )
            phone_number_formatted = phonenumbers.format_number(
                phone_number_parsed, phonenumbers.PhoneNumberFormat.E164
            )

            # Get or create an ATHM_Client instance
            _, client_created = ATHM_Client.objects.get_or_create(
                email=transaction_data["email"].strip(),
                phone_number=phone_number_formatted,
                defaults=dict(name=transaction_data["name"].strip()),
            )

            # Accumulate ATHM_Item instances in this list
            item_instances = [
                ATHM_Item(
                    transaction=transaction,
                    name=item.get("name", "")[:128],
                    description=item.get("description", "")[:255],
                    quantity=int(item.get("quantity", 1)),
                    price=_safe_decimal(item.get("price"), Decimal("0")),
                    tax=_safe_decimal(item.get("tax")),
                    metadata=item.get("metadata"),
                )
                for item in transaction_data.get("items", [])
            ]

            # Bulk create all ATHM_Item instances, if any
            if item_instances:
                ATHM_Item.objects.bulk_create(item_instances, ignore_conflicts=True)

            # Update counts to display later
            if transaction_created:
                total_transaction_created += 1
            else:
                total_transactions_updated += 1

            if client_created:
                total_clients_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {total_transaction_created} transaction(s), "
                f"updated {total_transactions_updated} transaction(s), "
                f"and created {total_clients_created} client(s)!"
            )
        )
