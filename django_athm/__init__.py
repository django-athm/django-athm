from django.apps import AppConfig

default_app_config = "django_athm.DjangoAthmAppConfig"


class DjangoAthmAppConfig(AppConfig):
    name = "django_athm"

    def ready(self):
        from . import signals  # noqa
