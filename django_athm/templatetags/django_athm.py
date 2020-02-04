import logging

from django import template
from django.conf import settings

register = template.Library()

logger = logging.getLogger(__name__)


@register.inclusion_tag("athm_button.html")
def athm_button(athm_config):
    logger.debug("[django_athm template:athm_button]")
    # TODO: Pre-process/validate data here

    return {
        "env": "sandbox" if settings.DJANGO_ATHM_SANDBOX_MODE else "production",
        "publicToken": athm_config.get(
            "public_token", settings.DJANGO_ATHM_PUBLIC_TOKEN
        ),
        "lang": athm_config.get("language", "en"),
        "timeout": athm_config.get("timeout", 600),
        "theme": athm_config.get("theme", "btn"),
        "total": athm_config["total"],
        "subtotal": athm_config["subtotal"],
        "items": athm_config["items"],
        "tax": athm_config["tax"],
        "metadata1": athm_config.get("metadata_1", ""),
        "metadata2": athm_config.get("metadata_2", ""),
    }
