import uuid
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.template.response import TemplateResponse
from django.utils import timezone

from django_athm.admin import (
    PaymentAdmin,
    PaymentLineItemAdmin,
    PaymentLineItemInline,
    RefundAdmin,
    WebhookEventAdmin,
)
from django_athm.models import Payment, PaymentLineItem, Refund, WebhookEvent

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

    def test_display_refundable_amount(self):
        payment_admin = PaymentAdmin(model=Payment, admin_site=admin.site)

        payment = Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="test",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            total_refunded_amount=Decimal("25.00"),
        )

        result = payment_admin.display_refundable_amount(payment)
        assert result == "$75.00"


class TestPaymentLineItemInline:
    def test_has_add_permission_returns_false(self, rf):
        request = setup_admin_request(rf, method="get")
        inline = PaymentLineItemInline(Payment, admin.site)
        assert inline.has_add_permission(request) is False


class TestPaymentLineItemAdmin:
    def test_transaction_link_with_payment(self):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-ref",
            status=Payment.Status.COMPLETED,
            total=Decimal("50.00"),
        )
        item = PaymentLineItem.objects.create(
            transaction=payment,
            name="Test Item",
            price=Decimal("50.00"),
        )

        item_admin = PaymentLineItemAdmin(model=PaymentLineItem, admin_site=admin.site)
        result = item_admin.transaction_link(item)

        assert "test-ref" in result
        assert f"/admin/django_athm/payment/{payment.ecommerce_id}/" in result

    def test_transaction_link_without_payment(self):
        item = Mock(spec=PaymentLineItem)
        item.transaction = None

        item_admin = PaymentLineItemAdmin(model=PaymentLineItem, admin_site=admin.site)
        result = item_admin.transaction_link(item)

        assert result == "-"


class TestRefundAdmin:
    def test_payment_link_with_payment(self):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-ref",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        refund = Refund.objects.create(
            payment=payment,
            reference_number="refund-ref",
            amount=Decimal("50.00"),
            transaction_date=timezone.now(),
        )

        refund_admin = RefundAdmin(model=Refund, admin_site=admin.site)
        result = refund_admin.payment_link(refund)

        assert "test-ref" in result
        assert f"/admin/django_athm/payment/{payment.ecommerce_id}/" in result

    def test_payment_link_without_payment(self):
        refund = Mock(spec=Refund)
        refund.payment = None

        refund_admin = RefundAdmin(model=Refund, admin_site=admin.site)
        result = refund_admin.payment_link(refund)

        assert result == "-"

    def test_display_amount_with_currency(self):
        refund = Mock(spec=Refund)
        refund.amount = Decimal("123.45")

        refund_admin = RefundAdmin(model=Refund, admin_site=admin.site)
        result = refund_admin.display_amount_with_currency(refund)

        assert result == "$123.45"


class TestWebhookEventAdmin:
    def test_display_id_short(self):
        event = WebhookEvent(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            idempotency_key="test-key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        result = event_admin.display_id_short(event)

        assert result == "12345678"

    def test_display_processed_icon(self):
        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)

        processed_event = WebhookEvent(
            idempotency_key="key1",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            processed=True,
        )
        unprocessed_event = WebhookEvent(
            idempotency_key="key2",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            processed=False,
        )

        assert event_admin.display_processed_icon(processed_event) is True
        assert event_admin.display_processed_icon(unprocessed_event) is False

    def test_transaction_link_with_transaction(self):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-ref",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        event = WebhookEvent.objects.create(
            idempotency_key="test-key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            transaction=payment,
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        result = event_admin.transaction_link(event)

        assert "test-ref" in result
        assert f"/admin/django_athm/payment/{payment.ecommerce_id}/" in result

    def test_transaction_link_without_transaction(self):
        event = WebhookEvent(
            idempotency_key="key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            transaction=None,
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        result = event_admin.transaction_link(event)

        assert result == "-"

    def test_payload_display(self):
        event = WebhookEvent(
            idempotency_key="key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={"test": "data", "number": 123},
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        result = event_admin.payload_display(event)

        assert "<pre>" in result
        # HTML-escaped quotes
        assert "&quot;test&quot;" in result or '"test"' in result

    def test_reprocess_events_success(self, rf, mocker):
        mocker.patch("django_athm.admin.WebhookProcessor.process")

        request = setup_admin_request(rf)

        event = WebhookEvent.objects.create(
            idempotency_key="unprocessed-key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            processed=False,
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        event_admin.reprocess_events(request, WebhookEvent.objects.filter(id=event.id))

        msgs = list(get_messages(request))
        assert "Successfully reprocessed 1 events" in str(msgs[0])

    def test_reprocess_events_with_errors(self, rf, mocker):
        mocker.patch(
            "django_athm.admin.WebhookProcessor.process",
            side_effect=Exception("Processing error"),
        )

        request = setup_admin_request(rf)

        event = WebhookEvent.objects.create(
            idempotency_key="error-key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            processed=False,
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        event_admin.reprocess_events(request, WebhookEvent.objects.filter(id=event.id))

        msgs = list(get_messages(request))
        assert "1 errors" in str(msgs[0])

    def test_reprocess_events_skips_already_processed(self, rf, mocker):
        mock_process = mocker.patch("django_athm.admin.WebhookProcessor.process")

        request = setup_admin_request(rf)

        event = WebhookEvent.objects.create(
            idempotency_key="processed-key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            processed=True,  # Already processed
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        event_admin.reprocess_events(request, WebhookEvent.objects.filter(id=event.id))

        mock_process.assert_not_called()
        msgs = list(get_messages(request))
        assert "No unprocessed events" in str(msgs[0])

    def test_install_webhooks_view_get(self, rf):
        request = setup_admin_request(rf, method="get")

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        response = event_admin.install_webhooks_view(request)

        assert isinstance(response, TemplateResponse)
        assert "install_webhooks.html" in response.template_name
        assert "form" in response.context_data

    def test_install_webhooks_view_post_success(self, rf, mocker):
        mock_client = Mock()
        mocker.patch(
            "django_athm.admin.PaymentService.get_client",
            return_value=mock_client,
        )

        request = setup_admin_request(
            rf, method="post", data={"url": "https://example.com/webhook/"}
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        response = event_admin.install_webhooks_view(request)

        mock_client.subscribe_webhook.assert_called_once_with(
            listener_url="https://example.com/webhook/"
        )
        assert response.status_code == 302  # Redirect on success

    def test_install_webhooks_view_post_invalid_url(self, rf):
        request = setup_admin_request(
            rf, method="post", data={"url": "not-a-valid-url"}
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        response = event_admin.install_webhooks_view(request)

        assert isinstance(response, TemplateResponse)
        assert response.context_data["form"].errors

    def test_install_webhooks_view_post_api_error(self, rf, mocker):
        mock_client = Mock()
        mock_client.subscribe_webhook.side_effect = Exception("API Error")
        mocker.patch(
            "django_athm.admin.PaymentService.get_client",
            return_value=mock_client,
        )

        request = setup_admin_request(
            rf, method="post", data={"url": "https://example.com/webhook/"}
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        event_admin.install_webhooks_view(request)

        msgs = list(get_messages(request))
        assert "Failed" in str(msgs[0])
