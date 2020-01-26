import debug_toolbar
from django.urls import include, path

from django_athm.ath_movil import views

urlpatterns = [
    path("", views.index),
    path("callback/", views.callback, name="athm_callback"),
    path("__debug__/", include(debug_toolbar.urls)),
]
