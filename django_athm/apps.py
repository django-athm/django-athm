from django.apps import AppConfig


class DjangoAthmAppConfig(AppConfig):
    name = "django_athm"

    def ready(self):
        from . import signals  # noqa
