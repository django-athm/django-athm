from django.apps import AppConfig


class TestAppConfig(AppConfig):
    name = "tests.apps.testapp"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import tests.apps.testapp.signals  # noqa: F401
