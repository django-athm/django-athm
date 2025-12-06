from django.urls import path

from django_athm.conf import settings as app_settings
from django_athm.views import default_callback
from django_athm.webhooks import webhook_view

app_name = "django_athm"

urlpatterns = [
    # Webhook endpoint (backend-first approach)
    path("webhook/", webhook_view, name="athm_webhook"),
    # Legacy callback endpoint (frontend-first approach, deprecated)
    path(
        "callback/",
        getattr(app_settings, "CALLBACK_VIEW", default_callback),
        name="athm_callback",
    ),
]
