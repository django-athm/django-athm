from django.urls import path

from django_athm.webhooks import webhook_view

app_name = "django_athm"

urlpatterns = [
    path("webhook/", webhook_view, name="athm_webhook"),
]
