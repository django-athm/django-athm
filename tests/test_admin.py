import pytest
from django.contrib import admin
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from django_athm.admin import ATHM_TransactionAdmin
from django_athm.models import ATHM_Transaction

pytestmark = pytest.mark.django_db


def dummy_get_response(request):
    return None


class TestAdminCommands:
    def test_athm_transaction_refund_success(self, rf, mock_http_adapter_post):
        mock_http_adapter_post.return_value.json.return_value = {
            "refundStatus": "COMPLETED",
            "refundedAmount": "25.50",
        }
        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        ATHM_Transaction.objects.create(
            reference_number="test-123",
            status=ATHM_Transaction.Status.COMPLETED,
            total=25.50,
            subtotal=23.10,
            tax=2.40,
            metadata_1="Metadata!",
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
        )

        ATHM_TransactionAdmin(model=ATHM_Transaction, admin_site=admin.site).refund(
            request=request,
            queryset=ATHM_Transaction.objects.filter(reference_number="test-123"),
        )

        updated_transaction = ATHM_Transaction.objects.get(reference_number="test-123")
        assert updated_transaction.status == ATHM_Transaction.Status.REFUNDED
        assert updated_transaction.refunded_amount == 25.50

        messages = get_messages(request)

        assert str(list(messages)[0]) == "Successfully refunded 1 transactions!"

    def test_athm_transaction_refund_failed(self, rf, mock_http_adapter_post):
        mock_http_adapter_post.return_value.json.return_value = {
            "errorCode": "5010",
            "description": "Transaction does not exist",
        }
        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        ATHM_Transaction.objects.create(
            reference_number="error",
            status=ATHM_Transaction.Status.COMPLETED,
            total=25.50,
            subtotal=23.10,
            tax=2.40,
            metadata_1="Metadata!",
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
        )

        ATHM_TransactionAdmin(model=ATHM_Transaction, admin_site=admin.site).refund(
            request=request,
            queryset=ATHM_Transaction.objects.filter(reference_number="error"),
        )

        messages = get_messages(request)

        assert str(list(messages)[0]) == "An error ocurred: Transaction does not exist"

    def test_athm_transaction_sync_success(self, rf, mock_http_adapter_post):
        """Test successful sync updates transaction status."""
        mock_http_adapter_post.return_value.json.return_value = {
            "status": "COMPLETED",
        }
        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        ATHM_Transaction.objects.create(
            reference_number="sync-test-123",
            status=ATHM_Transaction.Status.OPEN,
            total=50.00,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
        )

        ATHM_TransactionAdmin(model=ATHM_Transaction, admin_site=admin.site).sync(
            request=request,
            queryset=ATHM_Transaction.objects.filter(reference_number="sync-test-123"),
        )

        updated = ATHM_Transaction.objects.get(reference_number="sync-test-123")
        assert updated.status == ATHM_Transaction.Status.COMPLETED

        messages = list(get_messages(request))
        assert "Successfully synced 1 transactions!" in str(messages[0])

    def test_athm_transaction_sync_api_error(self, rf, mock_http_adapter_post):
        """Test sync handles API error response."""
        mock_http_adapter_post.return_value.json.return_value = {
            "errorCode": "5010",
            "description": "Transaction does not exist",
        }
        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        ATHM_Transaction.objects.create(
            reference_number="sync-error-test",
            status=ATHM_Transaction.Status.OPEN,
            total=50.00,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
        )

        ATHM_TransactionAdmin(model=ATHM_Transaction, admin_site=admin.site).sync(
            request=request,
            queryset=ATHM_Transaction.objects.filter(
                reference_number="sync-error-test"
            ),
        )

        # Status should not change on error
        unchanged = ATHM_Transaction.objects.get(reference_number="sync-error-test")
        assert unchanged.status == ATHM_Transaction.Status.OPEN

        messages = list(get_messages(request))
        assert "1 errors" in str(messages[0])

    def test_athm_transaction_sync_unknown_status(self, rf, mock_http_adapter_post):
        """Test sync handles unknown status from API."""
        mock_http_adapter_post.return_value.json.return_value = {
            "status": "UNKNOWN_STATUS",
        }
        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        ATHM_Transaction.objects.create(
            reference_number="sync-unknown-status",
            status=ATHM_Transaction.Status.OPEN,
            total=50.00,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
        )

        ATHM_TransactionAdmin(model=ATHM_Transaction, admin_site=admin.site).sync(
            request=request,
            queryset=ATHM_Transaction.objects.filter(
                reference_number="sync-unknown-status"
            ),
        )

        # Status should not change for unknown status
        unchanged = ATHM_Transaction.objects.get(reference_number="sync-unknown-status")
        assert unchanged.status == ATHM_Transaction.Status.OPEN

        messages = list(get_messages(request))
        assert "1 errors" in str(messages[0])

    def test_athm_transaction_sync_no_status_in_response(
        self, rf, mock_http_adapter_post
    ):
        """Test sync handles response without status field."""
        mock_http_adapter_post.return_value.json.return_value = {
            "someOtherField": "value",
        }
        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        ATHM_Transaction.objects.create(
            reference_number="sync-no-status",
            status=ATHM_Transaction.Status.OPEN,
            total=50.00,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
        )

        ATHM_TransactionAdmin(model=ATHM_Transaction, admin_site=admin.site).sync(
            request=request,
            queryset=ATHM_Transaction.objects.filter(reference_number="sync-no-status"),
        )

        # Status should not change
        unchanged = ATHM_Transaction.objects.get(reference_number="sync-no-status")
        assert unchanged.status == ATHM_Transaction.Status.OPEN

        messages = list(get_messages(request))
        assert "1 errors" in str(messages[0])

    def test_athm_transaction_sync_multiple_transactions(
        self, rf, mock_http_adapter_post
    ):
        """Test sync handles multiple transactions."""
        mock_http_adapter_post.return_value.json.return_value = {
            "status": "COMPLETED",
        }
        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        for i in range(3):
            ATHM_Transaction.objects.create(
                reference_number=f"sync-multi-{i}",
                status=ATHM_Transaction.Status.OPEN,
                total=50.00,
                date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
            )

        ATHM_TransactionAdmin(model=ATHM_Transaction, admin_site=admin.site).sync(
            request=request,
            queryset=ATHM_Transaction.objects.filter(
                reference_number__startswith="sync-multi-"
            ),
        )

        # All should be updated
        for i in range(3):
            txn = ATHM_Transaction.objects.get(reference_number=f"sync-multi-{i}")
            assert txn.status == ATHM_Transaction.Status.COMPLETED

        messages = list(get_messages(request))
        assert "Successfully synced 3 transactions!" in str(messages[0])

    def test_athm_transaction_sync_refunded_status(self, rf, mock_http_adapter_post):
        """Test sync correctly maps REFUNDED status."""
        mock_http_adapter_post.return_value.json.return_value = {
            "status": "REFUNDED",
        }
        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        ATHM_Transaction.objects.create(
            reference_number="sync-refunded",
            status=ATHM_Transaction.Status.COMPLETED,
            total=50.00,
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
        )

        ATHM_TransactionAdmin(model=ATHM_Transaction, admin_site=admin.site).sync(
            request=request,
            queryset=ATHM_Transaction.objects.filter(reference_number="sync-refunded"),
        )

        updated = ATHM_Transaction.objects.get(reference_number="sync-refunded")
        assert updated.status == ATHM_Transaction.Status.REFUNDED

    def test_athm_transaction_sync_empty_queryset(self, rf, mock_http_adapter_post):
        """Test sync handles empty queryset gracefully."""
        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        ATHM_TransactionAdmin(model=ATHM_Transaction, admin_site=admin.site).sync(
            request=request,
            queryset=ATHM_Transaction.objects.none(),
        )

        messages = list(get_messages(request))
        assert "Successfully synced 0 transactions!" in str(messages[0])
