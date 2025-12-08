import uuid
from decimal import Decimal

import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.template.response import TemplateResponse

from django_athm.admin import PaymentAdmin
from django_athm.models import Payment

pytestmark = pytest.mark.django_db


def dummy_get_response(request):
    return None


def setup_admin_request(rf, method="post", data=None):
    """Helper to create a request with session, messages, and admin user."""
    if method == "post":
        request = rf.post("/admin/django_athm/payment/", data=data or {})
    else:
        request = rf.get("/admin/django_athm/payment/")

    SessionMiddleware(dummy_get_response).process_request(request)
    MessageMiddleware(dummy_get_response).process_request(request)
    request.session.save()

    # Create admin user for admin context
    user, _ = User.objects.get_or_create(
        username="admin",
        defaults={"is_staff": True, "is_active": True, "is_superuser": True},
    )
    request.user = user
    return request


class TestPaymentAdmin:
    def test_refund_shows_confirmation_page(self, rf):
        """Test that selecting refund action shows confirmation page first."""
        request = setup_admin_request(rf)

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-123",
            status=Payment.Status.COMPLETED,
            total=Decimal("25.50"),
            subtotal=Decimal("23.10"),
            tax=Decimal("2.40"),
            net_amount=Decimal("25.50"),
            total_refunded_amount=Decimal("0.00"),
        )

        response = PaymentAdmin(
            model=Payment, admin_site=admin.site
        ).refund_selected_payments(
            request=request,
            queryset=Payment.objects.filter(ecommerce_id=payment.ecommerce_id),
        )

        assert isinstance(response, TemplateResponse)
        assert "refund_confirmation.html" in response.template_name
        assert payment in response.context_data["payments"]

    def test_refund_selected_payments_success(self, rf, mocker):
        """Test that confirmed refund executes successfully."""
        mock_refund = mocker.patch(
            "django_athm.admin.PaymentService.refund",
            return_value=mocker.Mock(reference_number="refund-123"),
        )

        request = setup_admin_request(rf, data={"confirm": "yes"})

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-123",
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

        mock_refund.assert_called_once()
        msgs = list(get_messages(request))
        assert "Refunded 1 payment(s)" in str(msgs[0])

    def test_refund_selected_payments_not_refundable(self, rf):
        """Test that non-refundable payments are filtered out."""
        request = setup_admin_request(rf)

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="not-completed",
            status=Payment.Status.OPEN,
            total=Decimal("25.50"),
            subtotal=Decimal("23.10"),
            tax=Decimal("2.40"),
        )

        response = PaymentAdmin(
            model=Payment, admin_site=admin.site
        ).refund_selected_payments(
            request=request,
            queryset=Payment.objects.filter(ecommerce_id=payment.ecommerce_id),
        )

        assert isinstance(response, TemplateResponse)
        assert len(response.context_data["payments"]) == 0

    def test_refund_selected_payments_api_error(self, rf, mocker):
        """Test that API errors during refund are handled gracefully."""
        mocker.patch(
            "django_athm.admin.PaymentService.refund",
            side_effect=Exception("API Error"),
        )

        request = setup_admin_request(rf, data={"confirm": "yes"})

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

        msgs = list(get_messages(request))
        assert "1 refund(s) failed" in str(msgs[0])

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
