import logging

from django import template

from django_athm.conf import settings as app_settings
from django_athm.constants import BUTTON_COLOR_DEFAULT, BUTTON_LANGUAGE_SPANISH

register = template.Library()

logger = logging.getLogger(__name__)


@register.inclusion_tag("athm_button.html")
def athm_button(athm_config):
    logger.debug("[django_athm:template:athm_button]")
    # TODO: Pre-process/validate data here

    return {
        "env": "sandbox" if app_settings.SANDBOX_MODE else "production",
        "publicToken": athm_config.get("public_token", app_settings.PUBLIC_TOKEN),
        "lang": athm_config.get("language", BUTTON_LANGUAGE_SPANISH),
        "timeout": athm_config.get("timeout", 600),
        "theme": athm_config.get("theme", BUTTON_COLOR_DEFAULT),
        "total": athm_config["total"],
        "subtotal": athm_config["subtotal"],
        "items": athm_config["items"],
        "tax": athm_config["tax"],
        "metadata1": athm_config.get("metadata_1", ""),
        "metadata2": athm_config.get("metadata_2", ""),
    }
