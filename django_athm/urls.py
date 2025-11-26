from django.urls import path

from django_athm.conf import settings as app_settings
from django_athm.views import default_callback

app_name = "django_athm"

urlpatterns = [
    path(
        "callback/",
        getattr(app_settings, "CALLBACK_VIEW", default_callback),
        name="athm_callback",
    ),
]
