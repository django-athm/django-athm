from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from django_athm.views import default_callback


def get_callback_function(setting_name, default):
    func = getattr(settings, setting_name, None)
    if not func:
        return default

    if callable(func):
        return func

    if isinstance(func, str):
        func = import_string(func)

    if not callable(func):
        raise ImproperlyConfigured("f{setting_name} must be callable.")

    return func


# Callback view
DJANGO_ATHM_CALLBACK_VIEW = get_callback_function(
    "DJANGO_ATHM_CALLBACK_VIEW", default_callback
)


# Sandbox Mode
SANDBOX_PUBLIC_TOKEN = "sandboxtoken01875617264"

if hasattr(settings, "DJANGO_ATHM_SANDBOX_MODE"):
    DJANGO_ATHM_SANDBOX_MODE = settings.DJANGO_ATHM_SANDBOX_MODE
else:
    DJANGO_ATHM_SANDBOX_MODE = False

# Public Token
if hasattr(settings, "DJANGO_ATHM_PUBLIC_TOKEN"):
    DJANGO_ATHM_PUBLIC_TOKEN = settings.DJANGO_ATHM_PUBLIC_TOKEN
else:
    if DJANGO_ATHM_SANDBOX_MODE:
        DJANGO_ATHM_PUBLIC_TOKEN = SANDBOX_PUBLIC_TOKEN
    else:
        raise ImproperlyConfigured("Missing DJANGO_ATHM_PUBLIC_TOKEN setting.")

# Private token
if hasattr(settings, "DJANGO_ATHM_PRIVATE_TOKEN"):
    DJANGO_ATHM_PRIVATE_TOKEN = settings.DJANGO_ATHM_PRIVATE_TOKEN
else:
    if not DJANGO_ATHM_SANDBOX_MODE:
        raise ImproperlyConfigured("Missing DJANGO_ATHM_PRIVATE_TOKEN setting.")
