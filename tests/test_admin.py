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
