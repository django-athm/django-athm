from decimal import Decimal

import pytest
from django.contrib import admin
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from django_athm.admin import ATHM_TransactionAdmin
from django_athm.models import Payment

pytestmark = pytest.mark.django_db


def dummy_get_response(request):
    return None


class TestAdminCommands:
    def test_athm_transaction_refund_success(self, rf, mocker):
        # Mock the ATHMClient refund_payment method
        mocker.patch(
            "django_athm.admin.ATHMClient.refund_payment",
            return_value={
                "refundStatus": "COMPLETED",
                "refundedAmount": "25.50",
            },
        )

        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        Payment.objects.create(
            reference_number="test-123",
            status=Payment.Status.COMPLETED,
            total=Decimal("25.50"),
            subtotal=Decimal("23.10"),
            tax=Decimal("2.40"),
            metadata_1="Metadata!",
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
        )

        ATHM_TransactionAdmin(model=Payment, admin_site=admin.site).refund_action(
            request=request,
            queryset=Payment.objects.filter(reference_number="test-123"),
        )

        updated_transaction = Payment.objects.get(reference_number="test-123")
        assert updated_transaction.status == Payment.Status.REFUNDED
        assert updated_transaction.refunded_amount == Decimal("25.50")

        messages = get_messages(request)
        assert "Successfully refunded 1 transactions" in str(list(messages)[0])

    def test_athm_transaction_refund_failed(self, rf, mocker):
        # Mock the ATHMClient to raise an error
        from athm.exceptions import ATHMovilError

        mocker.patch(
            "django_athm.admin.ATHMClient.refund_payment",
            side_effect=ATHMovilError("Transaction does not exist"),
        )

        request = rf.post(reverse("admin:django_athm_athm_transaction_changelist"))

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        Payment.objects.create(
            reference_number="error",
            status=Payment.Status.COMPLETED,
            total=Decimal("25.50"),
            subtotal=Decimal("23.10"),
            tax=Decimal("2.40"),
            metadata_1="Metadata!",
            date=make_aware(parse_datetime("2022-08-05 10:00:00.0")),
        )

        ATHM_TransactionAdmin(model=Payment, admin_site=admin.site).refund_action(
            request=request,
            queryset=Payment.objects.filter(reference_number="error"),
        )

        messages = get_messages(request)
        assert "Failed to refund transactions: 1 errors occurred" in str(
            list(messages)[0]
        )
