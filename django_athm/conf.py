from django.conf import settings as dj_settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import setting_changed
from django.utils.module_loading import import_string

from django_athm.views import default_callback

DEFAULTS = {
    "SANDBOX_PUBLIC_TOKEN": "sandboxtoken01875617264",
    "SANDBOX_MODE": True,
    "CALLBACK_VIEW": default_callback,
    "PUBLIC_TOKEN": None,
    "PRIVATE_TOKEN": None,
}


def is_callable(value):
    return callable(value) and not isinstance(value, type)


def get_callback_function(func):
    if is_callable(func):
        return func

    if isinstance(func, str):
        return import_string(func)

    raise ImproperlyConfigured(f"{func} must be callable.")


class Settings(object):
    def __getattr__(self, name):
        if name not in DEFAULTS:
            msg = "'%s' object has no attribute '%s'"
            raise AttributeError(msg % (self.__class__.__name__, name))

        value = self.get_setting(name)

        if is_callable(value):
            value = value()

        # Cache the result
        setattr(self, name, value)
        return value

    def get_setting(self, setting):
        django_setting = f"DJANGO_ATHM_{setting}"
        value = getattr(dj_settings, django_setting, DEFAULTS[setting])

        if setting == "CALLBACK_VIEW":
            return get_callback_function(value)

        return value

    def change_setting(self, setting, value, enter, **kwargs):
        if not setting.startswith("DJANGO_ATHM_"):
            return

        setting = setting.split("DJANGO_ATHM_")[1]  # strip 'DJANGO_ATHM_'

        # ensure a valid app setting is being overridden
        if setting not in DEFAULTS:
            return

        # if exiting, delete value to repopulate
        if enter:
            setattr(self, setting, value)
        else:
            delattr(self, setting)


settings = Settings()
setting_changed.connect(settings.change_setting)
