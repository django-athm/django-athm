import logging

from django import template

from django_athm.conf import settings as app_settings
from django_athm.constants import BUTTON_COLOR_DEFAULT, BUTTON_LANGUAGE_SPANISH

register = template.Library()

logger = logging.getLogger(__name__)


@register.inclusion_tag("athm_button.html", takes_context=True)
def athm_button(context, athm_config):
    """
    Render ATH Móvil payment button with backend-first modal flow.

    Usage:
        {% load django_athm %}
        {% athm_button config %}

    Config dict should contain:
        - total: Required, payment amount
        - subtotal: Optional
        - tax: Optional
        - metadata1: Optional, custom metadata field 1
        - metadata2: Optional, custom metadata field 2
        - language: Optional, 'en' or 'es' (default: 'es')
        - theme: Optional, 'btn', 'btn-light', or 'btn-dark' (default: 'btn')
        - timeout: Optional, seconds to wait for confirmation (default: 600)
    """
    logger.debug("[django_athm:template:athm_button]")

    return {
        "lang": athm_config.get("language", BUTTON_LANGUAGE_SPANISH),
        "timeout": athm_config.get("timeout", 600),
        "theme": athm_config.get("theme", BUTTON_COLOR_DEFAULT),
        "total": athm_config["total"],
        "subtotal": athm_config.get("subtotal", ""),
        "tax": athm_config.get("tax", ""),
        "metadata1": athm_config.get("metadata1", ""),
        "metadata2": athm_config.get("metadata2", ""),
        "csrf_token": context.get("csrf_token", ""),
    }
