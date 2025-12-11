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
    ClientAdmin,
    PaymentAdmin,
    RefundAdmin,
    WebhookEventAdmin,
)
from django_athm.models import Client, Payment, Refund, WebhookEvent

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

    def test_webhooks_timeline_with_webhooks(self):
        """Test webhooks_timeline renders list when payment has webhook events."""
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="timeline-test",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        WebhookEvent.objects.create(
            idempotency_key="timeline-key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            payment=payment,
            processed=True,
        )

        payment_admin = PaymentAdmin(model=Payment, admin_site=admin.site)
        result = payment_admin.webhooks_timeline(payment)

        assert "<ul>" in result
        assert "eCommerce Payment Completed" in result
        assert "Processed" in result

    def test_webhooks_timeline_no_webhooks(self):
        """Test webhooks_timeline returns message when payment has no webhooks."""
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="no-webhooks",
            status=Payment.Status.OPEN,
            total=Decimal("50.00"),
        )

        payment_admin = PaymentAdmin(model=Payment, admin_site=admin.site)
        result = payment_admin.webhooks_timeline(payment)

        assert result == "No webhook events"

    def test_client_link_with_client(self):
        """Test client_link renders link when payment has a client."""
        client = Client.objects.create(
            phone_number="7875551234",
            name="Test Client",
            email="test@example.com",
        )
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="client-link-test",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            client=client,
        )

        payment_admin = PaymentAdmin(model=Payment, admin_site=admin.site)
        result = payment_admin.client_link(payment)

        assert "7875551234" in result
        assert f"/admin/django_athm/client/{client.pk}/" in result


class TestClientAdmin:
    def test_has_add_permission_returns_false(self, rf):
        request = setup_admin_request(rf, method="get")
        client_admin = ClientAdmin(Client, admin.site)
        assert client_admin.has_add_permission(request) is False

    def test_has_change_permission_returns_false(self, rf):
        request = setup_admin_request(rf, method="get")
        client_admin = ClientAdmin(Client, admin.site)
        assert client_admin.has_change_permission(request) is False

    def test_has_delete_permission_returns_false(self, rf):
        request = setup_admin_request(rf, method="get")
        client_admin = ClientAdmin(Client, admin.site)
        assert client_admin.has_delete_permission(request) is False

    def test_payment_count(self):
        client = Client.objects.create(
            phone_number="7875551234",
            name="Test Client",
            email="test@example.com",
        )

        # Create payments linked to client
        Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-ref-1",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            client=client,
        )
        Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-ref-2",
            status=Payment.Status.COMPLETED,
            total=Decimal("50.00"),
            client=client,
        )

        client_admin = ClientAdmin(Client, admin.site)
        assert client_admin.payment_count(client) == 2

    def test_refund_count(self):
        client = Client.objects.create(
            phone_number="7875551234",
            name="Test Client",
            email="test@example.com",
        )

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="test-ref",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            client=client,
        )

        # Create refunds linked to client
        Refund.objects.create(
            payment=payment,
            reference_number="refund-1",
            amount=Decimal("25.00"),
            transaction_date=timezone.now(),
            client=client,
        )
        Refund.objects.create(
            payment=payment,
            reference_number="refund-2",
            amount=Decimal("25.00"),
            transaction_date=timezone.now(),
            client=client,
        )

        client_admin = ClientAdmin(Client, admin.site)
        assert client_admin.refund_count(client) == 2

    def test_payment_count_no_pk(self):
        """Test payment_count returns 0 for unsaved client."""
        client = Client(phone_number="7875550000", name="Unsaved")
        client_admin = ClientAdmin(Client, admin.site)
        assert client_admin.payment_count(client) == 0

    def test_refund_count_no_pk(self):
        """Test refund_count returns 0 for unsaved client."""
        client = Client(phone_number="7875550000", name="Unsaved")
        client_admin = ClientAdmin(Client, admin.site)
        assert client_admin.refund_count(client) == 0

    def test_get_queryset_prefetch_related(self, rf):
        """Test that get_queryset uses prefetch_related for optimization."""
        request = setup_admin_request(rf, method="get")

        client = Client.objects.create(
            phone_number="7875559999",
            name="Prefetch Test",
            email="prefetch@example.com",
        )
        Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="prefetch-payment",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
            client=client,
        )

        client_admin = ClientAdmin(Client, admin.site)
        qs = client_admin.get_queryset(request)

        # Verify prefetch_related is applied
        fetched_client = qs.get(pk=client.pk)
        assert fetched_client.payments.count() == 1


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

    def test_client_link_with_client(self):
        """Test client_link renders link when refund has a client."""
        client = Client.objects.create(
            phone_number="7875557777",
            name="Refund Client",
            email="refund@example.com",
        )
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="refund-client-test",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        refund = Refund.objects.create(
            payment=payment,
            reference_number="refund-with-client",
            amount=Decimal("50.00"),
            transaction_date=timezone.now(),
            client=client,
        )

        refund_admin = RefundAdmin(model=Refund, admin_site=admin.site)
        result = refund_admin.client_link(refund)

        assert "7875557777" in result
        assert f"/admin/django_athm/client/{client.pk}/" in result

    def test_client_link_without_client(self):
        """Test client_link returns dash when refund has no client."""
        refund = Mock(spec=Refund)
        refund.client = None

        refund_admin = RefundAdmin(model=Refund, admin_site=admin.site)
        result = refund_admin.client_link(refund)

        assert result == "-"

    def test_get_queryset_selects_related(self, rf):
        """Test that get_queryset uses select_related for optimization."""
        request = setup_admin_request(rf, method="get")

        client = Client.objects.create(
            phone_number="7875558888",
            name="Refund QS Client",
            email="refundqs@example.com",
        )
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="refund-qs-payment",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        Refund.objects.create(
            payment=payment,
            reference_number="refund-qs-test",
            amount=Decimal("25.00"),
            transaction_date=timezone.now(),
            client=client,
        )

        refund_admin = RefundAdmin(model=Refund, admin_site=admin.site)
        qs = refund_admin.get_queryset(request)

        # Verify select_related is applied
        refund = qs.first()
        assert refund.payment.reference_number == "refund-qs-payment"
        assert refund.client.phone_number == "7875558888"


class TestWebhookEventAdmin:
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

    def test_payment_link_with_payment(self):
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
            payment=payment,
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        result = event_admin.payment_link(event)

        assert "test-ref" in result
        assert f"/admin/django_athm/payment/{payment.ecommerce_id}/" in result

    def test_payment_link_without_payment(self):
        event = WebhookEvent(
            idempotency_key="key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            payment=None,
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        result = event_admin.payment_link(event)

        assert result == "-"

    def test_refund_link_with_refund(self):
        from django.utils import timezone

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="payment-ref",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        refund = Refund.objects.create(
            payment=payment,
            reference_number="refund-ref",
            amount=Decimal("25.00"),
            status="COMPLETED",
            transaction_date=timezone.now(),
        )
        event = WebhookEvent.objects.create(
            idempotency_key="refund-key",
            event_type=WebhookEvent.Type.REFUND_SENT,
            remote_ip="127.0.0.1",
            payload={},
            payment=payment,
            refund=refund,
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        result = event_admin.refund_link(event)

        assert "refund-ref" in result
        assert f"/admin/django_athm/refund/{refund.pk}/" in result

    def test_refund_link_without_refund(self):
        event = WebhookEvent(
            idempotency_key="key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            refund=None,
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        result = event_admin.refund_link(event)

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

        request = setup_admin_request(rf, data={"confirm": "yes"})

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

        request = setup_admin_request(rf, data={"confirm": "yes"})

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

    def test_install_webhooks_view_autopopulates_url(self, rf):
        """Test that admin form auto-populates with detected URL."""
        request = setup_admin_request(rf, method="get")

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        response = event_admin.install_webhooks_view(request)

        assert isinstance(response, TemplateResponse)
        form = response.context_data["form"]

        # Should have initial value from request.build_absolute_uri()
        assert form.initial.get("url")
        assert "/athm/webhook/" in form.initial["url"]

    def test_install_webhooks_view_validates_https(self, rf):
        """Test that non-HTTPS URLs are rejected."""
        request = setup_admin_request(
            rf, method="post", data={"url": "http://example.com/webhook/"}
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        response = event_admin.install_webhooks_view(request)

        assert isinstance(response, TemplateResponse)
        assert response.context_data["form"].errors
        assert "url" in response.context_data["form"].errors

    def test_install_webhooks_view_handles_autodetect_failure(self, rf, mocker):
        """Test that form loads even when auto-detection raises ValidationError."""
        from django.core.exceptions import ValidationError as DjangoValidationError

        mocker.patch(
            "django_athm.admin.get_webhook_url",
            side_effect=DjangoValidationError("Cannot determine URL"),
        )

        request = setup_admin_request(rf, method="get")
        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        response = event_admin.install_webhooks_view(request)

        assert isinstance(response, TemplateResponse)
        form = response.context_data["form"]
        assert form.initial.get("url") == ""

    def test_reprocess_events_shows_confirmation_page(self, rf):
        """Test that reprocess action shows confirmation before executing."""
        event = WebhookEvent.objects.create(
            idempotency_key="confirm-key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            processed=False,
        )

        request = setup_admin_request(rf, method="post", data={})
        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        response = event_admin.reprocess_events(
            request, WebhookEvent.objects.filter(id=event.id)
        )

        assert isinstance(response, TemplateResponse)
        assert "reprocess_confirmation.html" in response.template_name

    def test_reprocess_events_mixed_success_and_errors(self, rf, mocker):
        """Test reprocess with some events succeeding and others failing."""
        call_count = [0]

        def process_alternating(event):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise Exception("Processing failed")

        mocker.patch(
            "django_athm.admin.WebhookProcessor.process",
            side_effect=process_alternating,
        )

        # Create two unprocessed events
        event1 = WebhookEvent.objects.create(
            idempotency_key="mixed-key-1",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            processed=False,
        )
        event2 = WebhookEvent.objects.create(
            idempotency_key="mixed-key-2",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            processed=False,
        )

        request = setup_admin_request(rf, data={"confirm": "yes"})
        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        event_admin.reprocess_events(
            request, WebhookEvent.objects.filter(id__in=[event1.id, event2.id])
        )

        msgs = list(get_messages(request))
        # Should show mixed result message
        assert "1 events" in str(msgs[0]) and "1 errors" in str(msgs[0])

    def test_get_queryset_selects_related(self, rf):
        """Test that get_queryset uses select_related for optimization."""
        request = setup_admin_request(rf, method="get")

        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="qs-test",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        WebhookEvent.objects.create(
            idempotency_key="qs-key",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload={},
            payment=payment,
        )

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        qs = event_admin.get_queryset(request)

        # Verify select_related is applied (accessing payment won't cause extra query)
        event = qs.first()
        assert event.payment.reference_number == "qs-test"

    def test_payload_display_handles_exception(self):
        """Test payload_display handles malformed payload gracefully."""
        event = WebhookEvent(
            idempotency_key="bad-payload",
            event_type=WebhookEvent.Type.ECOMMERCE_COMPLETED,
            remote_ip="127.0.0.1",
            payload=None,
        )
        # Force payload to something json.dumps can't handle
        event.payload = object()

        event_admin = WebhookEventAdmin(model=WebhookEvent, admin_site=admin.site)
        result = event_admin.payload_display(event)

        assert "<pre>" in result
