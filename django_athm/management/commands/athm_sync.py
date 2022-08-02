from pprint import pprint

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from django_athm.conf import settings as app_settings
from django_athm.constants import TRANSACTION_STATUS, TRANSACTION_TYPE
from django_athm.models import ATHM_Client, ATHM_Item, ATHM_Transaction


def get_status(transaction):
    if transaction["transactionType"] == TRANSACTION_TYPE.REFUND:
        return TRANSACTION_STATUS.REFUNDED
    elif transaction["transactionType"] == TRANSACTION_TYPE.ECOMMERCE:
        if float(transaction["totalRefundAmount"]) > 0:
            return TRANSACTION_STATUS.REFUNDED
        else:
            return TRANSACTION_STATUS.COMPLETED

    return transaction["transactionType"]


def get_defaults(transaction):
    return dict(
        reference_number=transaction["referenceNumber"],
        status=get_status(transaction),
        date=make_aware(parse_datetime(transaction["date"])),
        total=float(transaction["total"]),
        tax=float(transaction["tax"]),
        refunded_amount=float(transaction.get("totalRefundAmount", 0)),
        subtotal=float(transaction["subtotal"]),
        metadata_1=transaction.get("metadata1", None),
        metadata_2=transaction.get("metadata2", None),
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

        pprint(report_data)

        if "errorMessage" in report_data:
            error_details = report_data["errorMessage"]
            raise CommandError(error_details)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully obtained {len(report_data)} transactions!"
            )
        )

        # Check which transactions are already in the database
        total_created = 0
        total_updated = 0

        self.stdout.write("Saving results to database...")

        # For each transaction, create or update an ATHM_Transaction instance
        for transaction in report_data:
            tx_instance, created = ATHM_Transaction.objects.update_or_create(
                reference_number=transaction["referenceNumber"],
                defaults=get_defaults(transaction),
            )

            # Get or create an ATHM_Client instance
            client_instance, created = ATHM_Client.objects.get_or_create()

            # Accumulate ATHM_Item instances in this list
            item_instances = [
                ATHM_Item(
                    transaction=tx_instance,
                    name=item["name"],
                    description=item["description"],
                    quantity=int(item["quantity"]),
                    price=float(item["price"]),
                    tax=float(item["price"]),
                    metadata=item["metadata"],
                )
                for item in transaction["items"]
            ]

            # Bulk create all ATHM_Item instances, if any
            if item_instances:
                ATHM_Item.objects.bulk_create(item_instances)

            # Update counts to display later
            if created:
                total_created += 1
            else:
                total_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {total_created} transactions and updated {total_updated} transactions!"
            )
        )
