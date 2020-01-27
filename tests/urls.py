from django.conf.urls import include
from django.contrib import admin
from django.http.response import HttpResponse
from django.urls import path

admin.autodiscover()


def empty_view(request):
    return HttpResponse()


app_name = "testapp"

urlpatterns = [
    path("home/", empty_view, name="home"),
    path("admin/", admin.site.urls),
    path("athm/", include("django_athm.urls", namespace="django_athm")),
    path("testapp/", include("tests.apps.testapp.urls")),
]
