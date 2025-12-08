import uuid
from decimal import Decimal

import pytest
from django.contrib import admin
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware

from django_athm.admin import PaymentAdmin
from django_athm.models import Payment

pytestmark = pytest.mark.django_db


def dummy_get_response(request):
    return None


class TestPaymentAdmin:
    def test_refund_selected_payments_success(self, rf, mocker):
        # Mock the PaymentService.refund method
        mock_refund = mocker.patch(
            "django_athm.admin.PaymentService.refund",
            return_value=mocker.Mock(reference_number="refund-123"),
        )

        request = rf.post("/admin/django_athm/payment/")

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-123",
            status=Payment.Status.COMPLETED,
            total=Decimal("25.50"),
            subtotal=Decimal("23.10"),
            tax=Decimal("2.40"),
            net_amount=Decimal("25.50"),
            total_refunded_amount=Decimal("0.00"),
            metadata_1="Metadata!",
        )

        PaymentAdmin(model=Payment, admin_site=admin.site).refund_selected_payments(
            request=request,
            queryset=Payment.objects.filter(ecommerce_id=payment.ecommerce_id),
        )

        mock_refund.assert_called_once()
        messages = list(get_messages(request))
        assert "Successfully refunded 1 payments" in str(messages[0])

    def test_refund_selected_payments_not_refundable(self, rf, mocker):
        request = rf.post("/admin/django_athm/payment/")

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        # Create a non-refundable payment (status=OPEN)
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="not-completed",
            status=Payment.Status.OPEN,
            total=Decimal("25.50"),
            subtotal=Decimal("23.10"),
            tax=Decimal("2.40"),
        )

        PaymentAdmin(model=Payment, admin_site=admin.site).refund_selected_payments(
            request=request,
            queryset=Payment.objects.filter(ecommerce_id=payment.ecommerce_id),
        )

        messages = list(get_messages(request))
        assert "Failed to refund payments: 1 errors occurred" in str(messages[0])

    def test_refund_selected_payments_api_error(self, rf, mocker):
        # Mock the PaymentService.refund to raise an error
        mocker.patch(
            "django_athm.admin.PaymentService.refund",
            side_effect=Exception("API Error"),
        )

        request = rf.post("/admin/django_athm/payment/")

        SessionMiddleware(dummy_get_response).process_request(request)
        MessageMiddleware(dummy_get_response).process_request(request)
        request.session.save()

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="api-error",
            status=Payment.Status.COMPLETED,
            total=Decimal("25.50"),
            subtotal=Decimal("23.10"),
            tax=Decimal("2.40"),
            net_amount=Decimal("25.50"),
            total_refunded_amount=Decimal("0.00"),
        )

        PaymentAdmin(model=Payment, admin_site=admin.site).refund_selected_payments(
            request=request,
            queryset=Payment.objects.filter(ecommerce_id=payment.ecommerce_id),
        )

        messages = list(get_messages(request))
        assert "Failed to refund payments: 1 errors occurred" in str(messages[0])

    def test_display_status_colored(self):
        payment_admin = PaymentAdmin(model=Payment, admin_site=admin.site)

        payment = Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="test",
            status=Payment.Status.COMPLETED,
            total=Decimal("10.00"),
        )

        result = payment_admin.display_status_colored(payment)
        assert "green" in result
        assert "Completed" in result

    def test_display_is_refundable(self):
        payment_admin = PaymentAdmin(model=Payment, admin_site=admin.site)

        refundable_payment = Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="test",
            status=Payment.Status.COMPLETED,
            total=Decimal("10.00"),
            net_amount=Decimal("10.00"),
            total_refunded_amount=Decimal("0.00"),
        )

        non_refundable_payment = Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="test2",
            status=Payment.Status.OPEN,
            total=Decimal("10.00"),
        )

        assert payment_admin.display_is_refundable(refundable_payment) is True
        assert payment_admin.display_is_refundable(non_refundable_payment) is False
