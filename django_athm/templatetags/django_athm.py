import json
import logging

from django import template
from django.utils.safestring import mark_safe

from django_athm.conf import settings as app_settings
from django_athm.constants import BUTTON_COLOR_DEFAULT, BUTTON_LANGUAGE_SPANISH

register = template.Library()

logger = logging.getLogger(__name__)


@register.inclusion_tag("athm_button.html", takes_context=True)
def athm_button(context, athm_config):
    logger.debug("[django_athm:template:athm_button]")

    # Validate and process data
    total = athm_config["total"]

    # Validate total amount range ($1.00-$1,500.00)
    if not (1.0 <= float(total) <= 1500.0):
        raise ValueError(
            f"Total amount must be between $1.00 and $1,500.00, got ${total}"
        )

    # Validate required metadata fields (ATH Movil API requires both)
    metadata_1 = athm_config.get("metadata_1", "")
    metadata_2 = athm_config.get("metadata_2", "")

    if not metadata_1:
        raise ValueError("metadata_1 is required by ATH Movil API")
    if not metadata_2:
        raise ValueError("metadata_2 is required by ATH Movil API")

    # Validate items array (ATH Movil API requires at least one item)
    items = athm_config.get("items", [])
    if not items:
        raise ValueError("items array is required by ATH Movil API")

    # Truncate metadata to 40 characters max (ATH Movil API limit)
    if len(metadata_1) > 40:
        logger.warning(
            f"metadata_1 exceeds 40 character limit, truncating: {metadata_1}"
        )
        metadata_1 = metadata_1[:40]

    if len(metadata_2) > 40:
        logger.warning(
            f"metadata_2 exceeds 40 character limit, truncating: {metadata_2}"
        )
        metadata_2 = metadata_2[:40]

    # ATH Movil v4 API Bug Workarounds:
    # - phone_number: Causes BTRA_0041 error if provided (popup always asks for it)
    # - theme: Only "btn" works (btn-light, btn-dark are broken)
    # - language: Only "es" works (en is broken)
    # These limitations are on ATH Movil's side. We ignore user values with a warning.

    if athm_config.get("phone_number"):
        logger.warning(
            "phone_number is ignored due to ATH Movil v4 API bug (BTRA_0041). "
            "The checkout modal will prompt the customer for their phone number."
        )

    theme = athm_config.get("theme", BUTTON_COLOR_DEFAULT)
    if theme != BUTTON_COLOR_DEFAULT:
        logger.warning(
            f"theme '{theme}' is ignored due to ATH Movil v4 API bug. "
            f"Only '{BUTTON_COLOR_DEFAULT}' is currently supported."
        )

    language = athm_config.get("language", BUTTON_LANGUAGE_SPANISH)
    if language != BUTTON_LANGUAGE_SPANISH:
        logger.warning(
            f"language '{language}' is ignored due to ATH Movil v4 API bug. "
            f"Only '{BUTTON_LANGUAGE_SPANISH}' is currently supported."
        )

    # Validate timeout range (120-600 seconds per API docs)
    timeout = athm_config.get("timeout", 600)
    if not (120 <= timeout <= 600):
        logger.warning(
            f"Timeout {timeout} outside recommended range (120-600s), using 600"
        )
        timeout = 600

    return {
        "csrf_token": context.get("csrf_token", ""),
        "env": "production",  # Only valid value per ATH Movil API (no sandbox mode)
        "publicToken": athm_config.get("public_token", app_settings.PUBLIC_TOKEN),
        "lang": BUTTON_LANGUAGE_SPANISH,  # Hardcoded due to ATH Movil bug
        "timeout": timeout,
        "theme": BUTTON_COLOR_DEFAULT,  # Hardcoded due to ATH Movil bug
        "total": total,
        "subtotal": athm_config.get("subtotal", 0),
        "items": mark_safe(json.dumps(items)),
        "tax": athm_config.get("tax", 0),
        "metadata1": metadata_1,
        "metadata2": metadata_2,
    }
