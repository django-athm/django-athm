import pytest

from django_athm.models import Client
from django_athm.services import ClientService

pytestmark = pytest.mark.django_db


class TestClientServiceGetOrUpdate:
    """Tests for ClientService.get_or_update() method."""

    def test_creates_new_client_with_phone(self):
        """Test that a new client is created with a valid phone number."""
        client = ClientService.get_or_update(
            phone_number="7875551234",
            name="John Doe",
            email="john@example.com",
        )

        assert client is not None
        assert client.phone_number == "7875551234"
        assert client.name == "John Doe"
        assert client.email == "john@example.com"
        assert Client.objects.count() == 1

    def test_returns_existing_client_without_updates(self):
        """Test that existing client is returned when no updates needed."""
        # Create existing client
        existing = Client.objects.create(
            phone_number="7875551234",
            name="John Doe",
            email="john@example.com",
        )

        # Call with same data
        client = ClientService.get_or_update(
            phone_number="7875551234",
            name="John Doe",
            email="john@example.com",
        )

        assert client.pk == existing.pk
        assert Client.objects.count() == 1

    def test_updates_client_name_when_different(self):
        """Test that client name is updated when different."""
        # Create existing client
        existing = Client.objects.create(
            phone_number="7875551234",
            name="John Doe",
            email="john@example.com",
        )

        # Call with different name
        client = ClientService.get_or_update(
            phone_number="7875551234",
            name="Jane Doe",
            email="john@example.com",
        )

        assert client.pk == existing.pk
        assert client.name == "Jane Doe"
        assert Client.objects.count() == 1

    def test_updates_client_email_when_different(self):
        """Test that client email is updated when different."""
        # Create existing client
        existing = Client.objects.create(
            phone_number="7875551234",
            name="John Doe",
            email="john@example.com",
        )

        # Call with different email
        client = ClientService.get_or_update(
            phone_number="7875551234",
            name="John Doe",
            email="jane@example.com",
        )

        assert client.pk == existing.pk
        assert client.email == "jane@example.com"
        assert Client.objects.count() == 1

    def test_does_not_overwrite_name_with_empty_string(self):
        """Test that empty name doesn't overwrite existing name."""
        # Create existing client with name
        existing = Client.objects.create(
            phone_number="7875551234",
            name="John Doe",
            email="john@example.com",
        )

        # Call with empty name
        client = ClientService.get_or_update(
            phone_number="7875551234",
            name="",
            email="john@example.com",
        )

        assert client.pk == existing.pk
        assert client.name == "John Doe"  # Unchanged

    def test_does_not_overwrite_email_with_empty_string(self):
        """Test that empty email doesn't overwrite existing email."""
        # Create existing client with email
        existing = Client.objects.create(
            phone_number="7875551234",
            name="John Doe",
            email="john@example.com",
        )

        # Call with empty email
        client = ClientService.get_or_update(
            phone_number="7875551234",
            name="John Doe",
            email="",
        )

        assert client.pk == existing.pk
        assert client.email == "john@example.com"  # Unchanged

    def test_returns_none_for_none_phone(self):
        """Test that None is returned when phone_number is None."""
        client = ClientService.get_or_update(
            phone_number=None,
            name="John Doe",
            email="john@example.com",
        )

        assert client is None
        assert Client.objects.count() == 0

    def test_returns_none_for_empty_phone(self):
        """Test that None is returned when phone_number is empty string."""
        client = ClientService.get_or_update(
            phone_number="",
            name="John Doe",
            email="john@example.com",
        )

        assert client is None
        assert Client.objects.count() == 0

    def test_normalizes_phone_number(self):
        """Test that phone numbers are normalized (digits only)."""
        # Create with formatted number
        client = ClientService.get_or_update(
            phone_number="(787) 555-1234",
            name="John Doe",
            email="john@example.com",
        )

        assert client is not None
        assert client.phone_number == "7875551234"

        # Should find same client with different format
        client2 = ClientService.get_or_update(
            phone_number="787-555-1234",
            name="John Doe",
            email="john@example.com",
        )

        assert client2.pk == client.pk
        assert Client.objects.count() == 1

    def test_creates_client_with_empty_defaults(self):
        """Test that client can be created with empty name/email."""
        client = ClientService.get_or_update(
            phone_number="7875551234",
            name="",
            email="",
        )

        assert client is not None
        assert client.phone_number == "7875551234"
        assert client.name == ""
        assert client.email == ""
