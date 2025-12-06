from django.urls import path

from django_athm.payment_views import create_payment_view, payment_status_view
from django_athm.webhooks import webhook_view

app_name = "django_athm"

urlpatterns = [
    # Webhook endpoint
    path("webhook/", webhook_view, name="athm_webhook"),
    # Payment creation and status
    path("create-payment/", create_payment_view, name="create_payment"),
    path("payment-status/<str:ecommerce_id>/", payment_status_view, name="payment_status"),
]
