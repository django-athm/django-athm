import logging

from django import template
from django.conf import settings

register = template.Library()

logger = logging.getLogger(__name__)


@register.inclusion_tag("athm_button.html", takes_context=True)
def athm_button(context):
    logger.debug("[django_athm template:athm_button]")

    # TODO: Pre-process/validate data here
    athm_config = context.get("ATHM_CONFIG")

    return {
        "env": "sandbox" if settings.DJANGO_ATHM_SANDBOX_MODE else "production",
        "public_token": settings.DJANGO_ATHM_PUBLIC_TOKEN,
        "lang": "en",
        "timeout": 100,
        "theme": "btn",
        "total": athm_config["total"],
        "subtotal": athm_config["subtotal"],
        "items": athm_config["items"],
        "tax": athm_config["tax"],
        "metadata_1": athm_config.get("metadata_1", None),
        "metadata_2": athm_config.get("metadata_2", None),
    }
