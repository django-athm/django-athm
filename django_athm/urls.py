from django.urls import path

from django_athm.ath_movil import views

urlpatterns = [
    path("", views.index),
]
