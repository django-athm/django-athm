import logging

from django import template

from django_athm.conf import settings as app_settings
from django_athm.constants import BUTTON_COLOR_DEFAULT, BUTTON_LANGUAGE_SPANISH

register = template.Library()

logger = logging.getLogger(__name__)


@register.inclusion_tag("athm_button.html")
def athm_button(athm_config):
    logger.debug("[django_athm:template:athm_button]")

    # Validate and process data
    total = athm_config["total"]

    # Validate total amount range ($1.00-$1,500.00)
    if not (1.0 <= float(total) <= 1500.0):
        raise ValueError(
            f"Total amount must be between $1.00 and $1,500.00, got ${total}"
        )

    # Validate required metadata fields (ATH Móvil API requires both)
    metadata_1 = athm_config.get("metadata_1", "")
    metadata_2 = athm_config.get("metadata_2", "")

    if not metadata_1:
        raise ValueError("metadata_1 is required by ATH Móvil API")
    if not metadata_2:
        raise ValueError("metadata_2 is required by ATH Móvil API")

    # Truncate metadata to 40 characters max (ATH Móvil API limit)
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

    # Get phone_number (defaults to settings if not provided per-transaction)
    phone_number = athm_config.get("phone_number", app_settings.PHONE_NUMBER)

    # Validate phone_number is provided (either in config or settings)
    if not phone_number:
        raise ValueError(
            "phone_number is required by ATH Móvil API. "
            "Provide it in athm_config or set DJANGO_ATHM_PHONE_NUMBER in settings."
        )

    # Convert phone_number to numeric type (API expects Number, not String)
    try:
        phone_number = (
            int(phone_number) if isinstance(phone_number, str) else phone_number
        )
    except (ValueError, TypeError) as err:
        raise ValueError(f"phone_number must be numeric, got: {phone_number}") from err

    # Validate timeout range (120-600 seconds per API docs)
    timeout = athm_config.get("timeout", 600)
    if not (120 <= timeout <= 600):
        logger.warning(
            f"Timeout {timeout} outside recommended range (120-600s), using 600"
        )
        timeout = 600

    athm_config = {
        "env": "production",  # Only valid value per ATH Móvil API (no sandbox mode exists)
        "publicToken": athm_config.get("public_token", app_settings.PUBLIC_TOKEN),
        "lang": athm_config.get("language", BUTTON_LANGUAGE_SPANISH),
        "timeout": timeout,
        "theme": athm_config.get("theme", BUTTON_COLOR_DEFAULT),
        "total": total,
        "subtotal": athm_config["subtotal"],
        "items": athm_config["items"],
        "tax": athm_config["tax"],
        "metadata1": metadata_1,
        "metadata2": metadata_2,
        "phone_number": phone_number,
    }

    return athm_config
