from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from django_athm.services.payment_service import PaymentService
from django_athm.utils import get_webhook_url, validate_webhook_url


class Command(BaseCommand):
    help = "Register webhook URL with ATH Móvil"

    def add_arguments(self, parser):
        parser.add_argument(
            "url",
            nargs="?",
            help="Webhook URL (uses DJANGO_ATHM_WEBHOOK_URL if not provided)",
        )

    def handle(self, *args, **options):
        url = options.get("url")

        if not url:
            try:
                url = get_webhook_url(request=None)
                self.stdout.write(f"Using: {url}")
            except ValidationError as e:
                raise CommandError(str(e)) from e

        try:
            url = validate_webhook_url(url)
        except ValidationError as e:
            raise CommandError(f"Invalid URL: {e}") from e

        try:
            client = PaymentService.get_client()
            client.subscribe_webhook(listener_url=url)
            self.stdout.write(self.style.SUCCESS(f"Installed: {url}"))
        except Exception as e:
            raise CommandError(f"Failed: {e}") from e
