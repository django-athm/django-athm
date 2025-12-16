import logging

from django_athm.models import Client
from django_athm.utils import normalize_phone_number

logger = logging.getLogger(__name__)


class ClientService:
    """Service for managing ATH Movil client records."""

    @classmethod
    def get_or_update(
        cls, phone_number: str | None, name: str = "", email: str = ""
    ) -> Client | None:
        """
        Get or create a Client record by normalized phone number.

        Updates name/email with latest information (latest wins strategy).

        Args:
            phone_number: Raw phone number from webhook/API
            name: Customer name
            email: Customer email

        Returns:
            Client instance or None if no valid phone number provided
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
                client.save(update_fields=["name", "email", "updated_at"])
                logger.debug("[django-athm] Updated client id=%s", client.pk)
        else:
            logger.info("[django-athm] Created new client id=%s", client.pk)

        return client
