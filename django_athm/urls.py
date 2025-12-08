from django.urls import path

from django_athm import views

app_name = "django_athm"

urlpatterns = [
    path("webhook/", views.webhook, name="webhook"),
    path("api/initiate/", views.initiate, name="initiate"),
    path("api/status/", views.status, name="status"),
    path("api/authorize/", views.authorize, name="authorize"),
    path("api/cancel/", views.cancel, name="cancel"),
]
