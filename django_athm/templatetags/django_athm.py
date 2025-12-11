import json
import logging

from django import template
from django.urls import reverse

from django_athm.constants import (
    BUTTON_COLOR_DEFAULT,
    BUTTON_LANGUAGE_DEFAULT,
    BUTTON_VALID_LANGUAGES,
    BUTTON_VALID_THEMES,
)

logger = logging.getLogger(__name__)

register = template.Library()


@register.inclusion_tag("django_athm/button.html", takes_context=True)
def athm_button(context, config):
    """
    Render an ATH Móvil payment button with modal.

    Usage:
        {% load django_athm %}
        {% athm_button ATHM_CONFIG %}

    Args:
        config: Dict with payment config keys:
            - total: Payment amount (required, 1.00-1500.00)
            - subtotal: Optional subtotal for display
            - tax: Optional tax amount
            - metadata_1: Custom field (max 40 chars)
            - metadata_2: Custom field (max 40 chars)
            - items: List of item dicts
            - theme: Button theme (btn, btn-dark, btn-light)
            - lang: Language code (es, en)
            - success_url: Redirect URL on success. Query params
              `reference_number` and `ecommerce_id` are appended
              automatically (e.g., "/thanks/" -> "/thanks/?reference_number=...&ecommerce_id=...")
            - failure_url: Redirect URL on failure
    """
    total = config.get("total")
    if total is None:
        raise ValueError("config must include 'total'")

    subtotal = config.get("subtotal")
    tax = config.get("tax")
    metadata_1 = config.get("metadata_1", "")
    metadata_2 = config.get("metadata_2", "")
    items = config.get("items")
    success_url = config.get("success_url", "")
    failure_url = config.get("failure_url", "")

    theme = config.get("theme") or BUTTON_COLOR_DEFAULT
    if theme not in BUTTON_VALID_THEMES:
        logger.warning(
            "Invalid theme '%s', using default '%s'", theme, BUTTON_COLOR_DEFAULT
        )
        theme = BUTTON_COLOR_DEFAULT

    language = config.get("lang") or BUTTON_LANGUAGE_DEFAULT
    if language not in BUTTON_VALID_LANGUAGES:
        logger.warning(
            "Invalid language '%s', using default '%s'",
            language,
            BUTTON_LANGUAGE_DEFAULT,
        )
        language = BUTTON_LANGUAGE_DEFAULT

    csrf_token = context.get("csrf_token", "")

    return {
        "total": str(total),
        "subtotal": str(subtotal) if subtotal else "",
        "tax": str(tax) if tax else "",
        "metadata_1": metadata_1[:40] if metadata_1 else "",
        "metadata_2": metadata_2[:40] if metadata_2 else "",
        "items_json": json.dumps(items) if items else "[]",
        "success_url": success_url,
        "failure_url": failure_url,
        "theme": theme,
        "language": language,
        "poll_interval": 5,
        "max_poll_attempts": 60,
        "initiate_url": reverse("django_athm:initiate"),
        "status_url": reverse("django_athm:status"),
        "authorize_url": reverse("django_athm:authorize"),
        "cancel_url": reverse("django_athm:cancel"),
        "csrf_token": csrf_token,
    }
