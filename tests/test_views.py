import pytest
from django.urls import reverse

from django_athm.models import ATHM_Client, ATHM_Item, ATHM_Transaction
from django_athm.views import default_callback


class TestDefaultCallbackView:
    """Tests for the ATH Movil v4 API callback view."""

    @pytest.mark.django_db
    def test_callback_view_with_v4_fields(self, rf):
        """Test callback with full v4 API response fields."""
        data = {
            "ecommerceStatus": "COMPLETED",
            "ecommerceId": "abc-123-def-456",
            "referenceNumber": "33908215-4028f9e06fd3c5c1016fdef4714a369a",
            "date": "2020-01-25 19:05:53.0",
            "total": "100.00",
            "tax": "7.00",
            "subtotal": "93.00",
            "fee": "2.50",
            "netAmount": "97.50",
            "metadata1": "Metadata 1",
            "metadata2": "Metadata 2",
            "customerName": "John Doe",
            "customerPhone": "+17875551234",
            "customerEmail": "john@example.com",
            "items": '[{"name":"First Item","description":"This is a description.","quantity":"1","price":"100.00","tax":"7.00","metadata":"metadata test"}]',
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 201

        # Verify transaction created with all v4 fields
        assert ATHM_Transaction.objects.count() == 1
        transaction = ATHM_Transaction.objects.first()
        assert transaction.status == ATHM_Transaction.Status.COMPLETED
        assert (
            transaction.reference_number == "33908215-4028f9e06fd3c5c1016fdef4714a369a"
        )
        assert transaction.ecommerce_id == "abc-123-def-456"
        assert transaction.ecommerce_status == "COMPLETED"
        assert transaction.total == 100.0
        assert transaction.tax == 7.0
        assert transaction.subtotal == 93.0
        assert transaction.fee == 2.5
        assert transaction.net_amount == 97.5
        assert transaction.customer_name == "John Doe"
        assert transaction.customer_phone == "+17875551234"

        # Verify client was created
        assert ATHM_Client.objects.count() == 1
        client = ATHM_Client.objects.first()
        assert client.name == "John Doe"
        assert client.email == "john@example.com"
        assert transaction.client == client

        # Verify items created
        assert ATHM_Item.objects.count() == 1
        item = ATHM_Item.objects.first()
        assert item.name == "First Item"
        assert item.price == 100.0
        assert item.tax == 7.0

    @pytest.mark.django_db
    def test_callback_view_with_minimal_data(self, rf):
        """Test callback with only required fields."""
        data = {
            "referenceNumber": "33908215-4028f9e06fd3c5c1016fdef4714a369a",
            "total": "1.0",
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 201

        assert ATHM_Transaction.objects.count() == 1
        transaction = ATHM_Transaction.objects.first()
        # Default status is COMPLETED when ecommerceStatus not provided
        assert transaction.status == ATHM_Transaction.Status.COMPLETED
        assert (
            transaction.reference_number == "33908215-4028f9e06fd3c5c1016fdef4714a369a"
        )
        assert transaction.total == 1.0
        assert transaction.client is None  # No customer data provided

    @pytest.mark.django_db
    def test_callback_creates_client(self, rf):
        """Test that callback creates ATHM_Client from customer data."""
        data = {
            "referenceNumber": "ref-create-client",
            "total": "50.00",
            "customerName": "Jane Smith",
            "customerPhone": "+17879876543",
            "customerEmail": "jane@example.com",
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 201

        # Client should be created
        assert ATHM_Client.objects.count() == 1
        client = ATHM_Client.objects.first()
        assert client.name == "Jane Smith"
        assert client.email == "jane@example.com"
        assert "+17879876543" in client.phone_number

        # Transaction should be linked to client
        transaction = ATHM_Transaction.objects.first()
        assert transaction.client == client

    @pytest.mark.django_db
    def test_callback_updates_existing_client(self, rf):
        """Test that callback updates existing client info."""
        # Create existing client
        client = ATHM_Client.objects.create(
            phone_number="+17875551234",
            name="Old Name",
            email="old@example.com",
        )

        data = {
            "referenceNumber": "ref-update-client",
            "total": "25.00",
            "customerName": "New Name",
            "customerPhone": "+17875551234",
            "customerEmail": "new@example.com",
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 201

        # Should still have only 1 client (updated, not created)
        assert ATHM_Client.objects.count() == 1
        client.refresh_from_db()
        assert client.name == "New Name"
        assert client.email == "new@example.com"

    @pytest.mark.django_db
    def test_callback_with_empty_phone(self, rf):
        """Test that callback handles empty phone gracefully (no client created)."""
        data = {
            "referenceNumber": "ref-empty-phone",
            "total": "10.00",
            "customerName": "Test User",
            "customerPhone": "",  # Empty phone
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        # Should succeed without client (empty phone triggers no client creation)
        assert response.status_code == 201
        assert ATHM_Transaction.objects.count() == 1
        assert ATHM_Client.objects.count() == 0  # No client created for empty phone
        transaction = ATHM_Transaction.objects.first()
        assert transaction.client is None

    @pytest.mark.django_db
    def test_callback_missing_required_fields(self, rf):
        """Test callback returns 400 when required fields missing."""
        # Missing referenceNumber
        data = {
            "total": "10.00",
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 400

        # Missing total
        data = {
            "referenceNumber": "ref-missing-total",
        }
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 400

    @pytest.mark.django_db
    def test_callback_with_invalid_json_items(self, rf):
        """Test callback handles invalid JSON in items field."""
        data = {
            "referenceNumber": "ref-invalid-json",
            "total": "10.00",
            "items": "not valid json",  # Invalid JSON
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        # Should succeed but with no items
        assert response.status_code == 201
        assert ATHM_Transaction.objects.count() == 1
        assert ATHM_Item.objects.count() == 0

    @pytest.mark.django_db
    def test_callback_status_mapping(self, rf):
        """Test ecommerceStatus to internal status mapping."""
        status_mapping = {
            "COMPLETED": ATHM_Transaction.Status.COMPLETED,
            "CANCEL": ATHM_Transaction.Status.CANCEL,
            "OPEN": ATHM_Transaction.Status.OPEN,
            "CONFIRM": ATHM_Transaction.Status.CONFIRM,
        }

        for api_status, expected_status in status_mapping.items():
            ATHM_Transaction.objects.all().delete()  # Clean up

            data = {
                "referenceNumber": f"ref-status-{api_status.lower()}",
                "total": "10.00",
                "ecommerceStatus": api_status,
            }

            url = reverse("django_athm:athm_callback")
            request = rf.post(url, data=data)
            response = default_callback(request)

            assert response.status_code == 201
            transaction = ATHM_Transaction.objects.first()
            assert transaction.status == expected_status, f"Failed for {api_status}"
