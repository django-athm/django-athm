import json
import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import Client

from django_athm.models import Payment, Refund, WebhookEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def payment():
    return Payment.objects.create(
        ecommerce_id=uuid.uuid4(),
        reference_number="test-ref-123",
        status=Payment.Status.OPEN,
        total=Decimal("100.00"),
    )


class TestWebhookView:
    def test_accepts_post_request(self, client):
        response = client.post(
            "/athm/webhook/",
            data=json.dumps({"test": "data"}),
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_rejects_get_request(self, client):
        response = client.get("/athm/webhook/")
        assert response.status_code == 405

    def test_handles_malformed_json(self, client):
        response = client.post(
            "/athm/webhook/",
            data="not valid json",
            content_type="application/json",
        )
        assert response.status_code == 200  # Always returns 200

    def test_creates_webhook_event(self, client):
        payload = {
            "eCommerceId": str(uuid.uuid4()),
            "status": "COMPLETED",
            "referenceNumber": "ref-123",
            "total": 100.00,
        }
        client.post(
            "/athm/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert WebhookEvent.objects.count() == 1

    @pytest.mark.django_db(transaction=True)
    def test_duplicate_webhook_not_reprocessed(self, client):
        payload = {
            "eCommerceId": str(uuid.uuid4()),
            "status": "COMPLETED",
            "referenceNumber": "ref-123",
            "total": 100.00,
        }
        # Send same payload twice
        client.post(
            "/athm/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        client.post(
            "/athm/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        # Only one event should be created
        assert WebhookEvent.objects.count() == 1

    def test_extracts_client_ip_from_x_forwarded_for(self, client):
        payload = {"test": "data"}
        client.post(
            "/athm/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_FORWARDED_FOR="203.0.113.195, 70.41.3.18",
        )
        event = WebhookEvent.objects.first()
        assert event.remote_ip == "203.0.113.195"

    @pytest.mark.django_db(transaction=True)
    def test_duplicate_refund_webhook_not_reprocessed(self, client):
        """Verify refund webhooks are idempotent at HTTP level."""
        # Create payment first
        Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="ref-for-refund",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )

        refund_payload = {
            "transactionType": "REFUND",
            "status": "COMPLETED",
            "referenceNumber": "ref-for-refund",
            "dailyTransactionId": "5678",
            "name": "Test Customer",
            "phoneNumber": "7871234567",
            "email": "test@example.com",
            "total": 25.00,
            "date": "2024-01-15 10:30:00",
        }

        # Send same refund webhook twice
        client.post(
            "/athm/webhook/",
            data=json.dumps(refund_payload),
            content_type="application/json",
        )
        client.post(
            "/athm/webhook/",
            data=json.dumps(refund_payload),
            content_type="application/json",
        )

        # Only one webhook event and one refund should be created
        assert WebhookEvent.objects.count() == 1
        assert Refund.objects.filter(reference_number="ref-for-refund").count() == 1


class TestInitiateView:
    def test_rejects_get_request(self, client):
        response = client.get("/athm/api/initiate/")
        assert response.status_code == 405

    def test_rejects_invalid_json(self, client):
        response = client.post(
            "/athm/api/initiate/",
            data="not json",
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"] == "Invalid JSON"

    def test_validates_total_required(self, client):
        response = client.post(
            "/athm/api/initiate/",
            data=json.dumps({"phone_number": "7875551234"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "Invalid total" in response.json()["error"]

    def test_validates_phone_number_required(self, client):
        response = client.post(
            "/athm/api/initiate/",
            data=json.dumps({"total": "100.00"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "Invalid phone number" in response.json()["error"]

    @patch("django_athm.views.PaymentService.initiate")
    def test_creates_payment_successfully(self, mock_initiate, client):
        mock_payment = Payment(
            ecommerce_id=uuid.uuid4(),
            reference_number="",
            status=Payment.Status.OPEN,
            total=Decimal("100.00"),
        )
        mock_initiate.return_value = (mock_payment, "auth-token-123")

        response = client.post(
            "/athm/api/initiate/",
            data=json.dumps({"total": "100.00", "phone_number": "7875551234"}),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ecommerce_id"] == str(mock_payment.ecommerce_id)
        assert data["status"] == "OPEN"

    @patch("django_athm.views.PaymentService.initiate")
    def test_stores_auth_token_in_session(self, mock_initiate, client):
        ecommerce_id = uuid.uuid4()
        mock_payment = Payment(
            ecommerce_id=ecommerce_id,
            reference_number="",
            status=Payment.Status.OPEN,
            total=Decimal("100.00"),
        )
        mock_initiate.return_value = (mock_payment, "auth-token-123")

        client.post(
            "/athm/api/initiate/",
            data=json.dumps({"total": "100.00", "phone_number": "7875551234"}),
            content_type="application/json",
        )

        session = client.session
        assert session[f"athm_auth_{ecommerce_id}"] == "auth-token-123"

    @patch("django_athm.views.PaymentService.initiate")
    def test_handles_service_error(self, mock_initiate, client):
        mock_initiate.side_effect = Exception("API Error")

        response = client.post(
            "/athm/api/initiate/",
            data=json.dumps({"total": "100.00", "phone_number": "7875551234"}),
            content_type="application/json",
        )

        assert response.status_code == 500
        assert "API Error" in response.json()["error"]


class TestStatusView:
    def test_rejects_post_request(self, client):
        response = client.post("/athm/api/status/")
        assert response.status_code == 405

    def test_requires_ecommerce_id(self, client):
        response = client.get("/athm/api/status/")
        assert response.status_code == 400
        assert response.json()["error"] == "Missing ecommerce_id"

    def test_validates_ecommerce_id_format(self, client):
        response = client.get("/athm/api/status/", {"ecommerce_id": "not-a-uuid"})
        assert response.status_code == 400
        assert response.json()["error"] == "Invalid ecommerce_id"

    def test_returns_404_for_missing_payment(self, client):
        response = client.get("/athm/api/status/", {"ecommerce_id": str(uuid.uuid4())})
        assert response.status_code == 404
        assert response.json()["error"] == "Payment not found"

    @patch("django_athm.views.PaymentService.sync_status")
    def test_returns_payment_status(self, mock_sync, client, payment):
        response = client.get(
            "/athm/api/status/", {"ecommerce_id": str(payment.ecommerce_id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OPEN"
        assert data["reference_number"] == "test-ref-123"

    @patch("django_athm.views.PaymentService.sync_status")
    def test_syncs_status_with_remote(self, mock_sync, client, payment):
        client.get("/athm/api/status/", {"ecommerce_id": str(payment.ecommerce_id)})
        mock_sync.assert_called_once_with(payment)


class TestAuthorizeView:
    def test_rejects_get_request(self, client):
        response = client.get("/athm/api/authorize/")
        assert response.status_code == 405

    def test_rejects_invalid_json(self, client):
        response = client.post(
            "/athm/api/authorize/",
            data="not json",
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"] == "Invalid JSON"

    def test_requires_ecommerce_id(self, client):
        response = client.post(
            "/athm/api/authorize/",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"] == "Missing ecommerce_id"

    def test_validates_ecommerce_id_format(self, client):
        response = client.post(
            "/athm/api/authorize/",
            data=json.dumps({"ecommerce_id": "not-a-uuid"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"] == "Invalid ecommerce_id"

    def test_requires_auth_token_in_session(self, client, payment):
        response = client.post(
            "/athm/api/authorize/",
            data=json.dumps({"ecommerce_id": str(payment.ecommerce_id)}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"] == "Session expired"

    def test_returns_404_for_missing_payment(self, client):
        ecommerce_id = uuid.uuid4()
        session = client.session
        session[f"athm_auth_{ecommerce_id}"] = "auth-token"
        session.save()

        response = client.post(
            "/athm/api/authorize/",
            data=json.dumps({"ecommerce_id": str(ecommerce_id)}),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_returns_existing_completed_payment(self, client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="completed-ref",
            status=Payment.Status.COMPLETED,
            total=Decimal("100.00"),
        )
        session = client.session
        session[f"athm_auth_{payment.ecommerce_id}"] = "auth-token"
        session.save()

        response = client.post(
            "/athm/api/authorize/",
            data=json.dumps({"ecommerce_id": str(payment.ecommerce_id)}),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.json()["status"] == "COMPLETED"
        assert response.json()["reference_number"] == "completed-ref"

    def test_rejects_cancelled_payment(self, client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="cancelled-ref",
            status=Payment.Status.CANCEL,
            total=Decimal("100.00"),
        )
        session = client.session
        session[f"athm_auth_{payment.ecommerce_id}"] = "auth-token"
        session.save()

        response = client.post(
            "/athm/api/authorize/",
            data=json.dumps({"ecommerce_id": str(payment.ecommerce_id)}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["error"] == "Payment was cancelled"

    def test_rejects_expired_payment(self, client):
        payment = Payment.objects.create(
            ecommerce_id=uuid.uuid4(),
            reference_number="expired-ref",
            status=Payment.Status.EXPIRED,
            total=Decimal("100.00"),
        )
        session = client.session
        session[f"athm_auth_{payment.ecommerce_id}"] = "auth-token"
        session.save()

        response = client.post(
            "/athm/api/authorize/",
            data=json.dumps({"ecommerce_id": str(payment.ecommerce_id)}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["error"]

    @patch("django_athm.views.PaymentService.authorize")
    def test_authorizes_payment_successfully(self, mock_authorize, client, payment):
        mock_authorize.return_value = "new-reference-number"

        session = client.session
        session[f"athm_auth_{payment.ecommerce_id}"] = "auth-token"
        session.save()

        response = client.post(
            "/athm/api/authorize/",
            data=json.dumps({"ecommerce_id": str(payment.ecommerce_id)}),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["reference_number"] == "new-reference-number"

    @patch("django_athm.views.PaymentService.authorize")
    def test_cleans_up_session_after_authorization(
        self, mock_authorize, client, payment
    ):
        mock_authorize.return_value = "new-reference-number"

        session = client.session
        session[f"athm_auth_{payment.ecommerce_id}"] = "auth-token"
        session.save()

        client.post(
            "/athm/api/authorize/",
            data=json.dumps({"ecommerce_id": str(payment.ecommerce_id)}),
            content_type="application/json",
        )

        session = client.session
        assert f"athm_auth_{payment.ecommerce_id}" not in session

    @patch("django_athm.views.PaymentService.authorize")
    def test_handles_authorization_error(self, mock_authorize, client, payment):
        mock_authorize.side_effect = Exception("Authorization failed")

        session = client.session
        session[f"athm_auth_{payment.ecommerce_id}"] = "auth-token"
        session.save()

        response = client.post(
            "/athm/api/authorize/",
            data=json.dumps({"ecommerce_id": str(payment.ecommerce_id)}),
            content_type="application/json",
        )

        assert response.status_code == 500
        assert "Authorization failed" in response.json()["error"]


class TestCancelView:
    def test_rejects_get_request(self, client):
        response = client.get("/athm/api/cancel/")
        assert response.status_code == 405

    def test_rejects_invalid_json(self, client):
        response = client.post(
            "/athm/api/cancel/",
            data="not json",
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"] == "Invalid JSON"

    def test_requires_ecommerce_id(self, client):
        response = client.post(
            "/athm/api/cancel/",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"] == "Missing ecommerce_id"

    def test_validates_ecommerce_id_format(self, client):
        response = client.post(
            "/athm/api/cancel/",
            data=json.dumps({"ecommerce_id": "not-a-uuid"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"] == "Invalid ecommerce_id"

    @patch("django_athm.views.PaymentService.cancel")
    def test_cancels_payment_successfully(self, mock_cancel, client, payment):
        response = client.post(
            "/athm/api/cancel/",
            data=json.dumps({"ecommerce_id": str(payment.ecommerce_id)}),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        mock_cancel.assert_called_once_with(payment.ecommerce_id)

    @patch("django_athm.views.PaymentService.cancel")
    def test_cleans_up_session_after_cancellation(self, mock_cancel, client, payment):
        session = client.session
        session[f"athm_auth_{payment.ecommerce_id}"] = "auth-token"
        session.save()

        client.post(
            "/athm/api/cancel/",
            data=json.dumps({"ecommerce_id": str(payment.ecommerce_id)}),
            content_type="application/json",
        )

        session = client.session
        assert f"athm_auth_{payment.ecommerce_id}" not in session

    @patch("django_athm.views.PaymentService.cancel")
    def test_returns_success_even_on_cancel_failure(self, mock_cancel, client, payment):
        mock_cancel.side_effect = Exception("Cancel failed")

        response = client.post(
            "/athm/api/cancel/",
            data=json.dumps({"ecommerce_id": str(payment.ecommerce_id)}),
            content_type="application/json",
        )

        # Should still return success
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
