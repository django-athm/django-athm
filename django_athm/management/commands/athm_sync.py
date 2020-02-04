import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from django_athm.constants import REFUNDED_STATUS
from django_athm.models import ATHM_Item, ATHM_Transaction


def get_status(transaction):
    if transaction["transactionType"] == "refund":
        return REFUNDED_STATUS
    else:
        return transaction["status"]


def get_defaults(transaction):
    return dict(
        reference_number=transaction["referenceNumber"],
        status=get_status(transaction),
        date=make_aware(parse_datetime(transaction["date"])),
        total=float(transaction["total"]),
        tax=float(transaction["tax"]),
        refunded_amount=float(transaction["refundedAmount"]),
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
            default=settings.DJANGO_ATHM_PUBLIC_TOKEN,
            help="Your ATH Móvil Business public token. Default = settings.DJANGO_ATHM_PUBLIC_TOKEN",
            metavar="ATHM_PUBLIC_TOKEN",
        )

        parser.add_argument(
            "--private-token",
            type=str,
            required=False,
            default=settings.DJANGO_ATHM_PRIVATE_TOKEN,
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

        difference = end_date - start_date

        if difference.days < 0:
            raise CommandError("Start date must be before end date!")

        self.stdout.write(
            self.style.WARNING(
                f"Getting transactions from {start_date} to {end_date}..."
            )
        )

        athm_transactions = ATHM_Transaction.list(
            start_date=start_date,
            end_date=end_date,
            public_token=public_token,
            private_token=private_token,
        )

        self.stdout.write(self.style.SUCCESS("Successfully obtained transactions!"))

        # Check which transactions are already in the database
        total_created = 0
        total_updated = 0

        self.stdout.write(self.style.WARNING(f"Saving results to database..."))
        for transaction in athm_transactions:
            (
                transaction_instance,
                transaction_created,
            ) = ATHM_Transaction.objects.update_or_create(
                reference_number=transaction["referenceNumber"],
                defaults=get_defaults(transaction),
            )

            items = json.loads(transaction["items"])

            # Remove all existing items before recreating them if this transaction
            # previously existed
            if not transaction_created:
                ATHM_Item.objects.filter(transaction=transaction_instance).delete()

            item_instances = []

            for item in items:
                item_instances.append(
                    ATHM_Item(
                        transaction=transaction_instance,
                        name=item["name"],
                        description=item["description"],
                        quantity=int(item["quantity"]),
                        price=float(item["price"]),
                        tax=float(item["price"]),
                        metadata=item["metadata"],
                    )
                )

            if item_instances:
                ATHM_Item.objects.bulk_create(item_instances)

            if transaction_created:
                total_created += 1
            else:
                total_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {total_created} transactions and updated {total_updated} transactions!"
            )
        )
