import debug_toolbar
from django.conf import settings
from django.urls import include, path

from django_athm import views

app_name = "django_athm"

urlpatterns = [
    path("callback/", views.default_callback, name="athm_callback"),
]

if settings.DEBUG:
    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
