from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DjangoAthmAppConfig(AppConfig):
    default = True
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_athm"
    verbose_name = _("Django ATH Móvil")
