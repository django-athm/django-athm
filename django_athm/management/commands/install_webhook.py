from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator

from django_athm.services.payment_service import PaymentService


class Command(BaseCommand):
    help = "Register a webhook URL with ATH Móvil"

    def add_arguments(self, parser):
        parser.add_argument("url", help="Webhook URL (must be HTTPS)")

    def handle(self, *args, **options):
        url = options["url"]

        validator = URLValidator(schemes=["https"])
        try:
            validator(url)
        except ValidationError:
            raise CommandError("URL must use HTTPS scheme") from None

        try:
            client = PaymentService.get_client()
            client.subscribe_webhook(listener_url=url)
            self.stdout.write(self.style.SUCCESS(f"Webhook installed: {url}"))
        except Exception as e:
            raise CommandError(f"Failed to install webhook: {e}") from e
