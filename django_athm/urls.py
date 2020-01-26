import debug_toolbar
from django.urls import include, path

from django_athm import views

app_name = "django_athm"

urlpatterns = [
    path("", views.index),
    path("callback/", views.default_callback, name="athm_callback"),
    path("__debug__/", include(debug_toolbar.urls)),
]
