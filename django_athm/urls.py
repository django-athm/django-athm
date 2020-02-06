from django.urls import path

from django_athm import views

app_name = "django_athm"

urlpatterns = [
    path("callback/", views.default_callback, name="athm_callback"),
]
