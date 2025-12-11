from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.urls import reverse

from django_athm.conf import settings


def safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """
    Safely convert a value to Decimal.

    Args:
        value: Value to convert (int, float, str, Decimal, None)
        default: Default value if conversion fails or value is None

    Returns:
        Decimal value
    """
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return default


def validate_total(value: Any) -> Decimal:
    """
    Validate that total is a valid decimal between 1.00 and 1500.00.

    Returns:
        Decimal total if valid

    Raises:
        ValidationError: If invalid
    """
    if value is None:
        raise ValidationError("Invalid total")

    try:
        total = Decimal(str(value)) if not isinstance(value, Decimal) else value
    except (ValueError, TypeError, ArithmeticError) as e:
        raise ValidationError("Invalid total") from e

    if total < Decimal("1.00") or total > Decimal("1500.00"):
        raise ValidationError("Total must be between 1.00 and 1500.00")

    return total


def validate_phone_number(value: Any) -> str:
    """
    Validate and normalize phone number.
    Must be 10 digits.
    """
    phone = str(value or "").replace("-", "").replace(" ", "").strip()

    if not phone or len(phone) != 10 or not phone.isdigit():
        raise ValidationError("Invalid phone number")

    return phone


def normalize_phone_number(phone: str | None) -> str:
    """
    Normalize phone number to digits only.

    Used for Client model phone_number field to enable consistent
    matching across different webhook payloads.

    Args:
        phone: Raw phone number (may include spaces, dashes, parentheses)

    Returns:
        Phone number with only digits, or empty string if None/empty
    """
    if not phone:
        return ""
    return "".join(c for c in str(phone) if c.isdigit())


def get_webhook_url(request=None):
    """
    Resolve webhook URL.

    Priority:
    1. DJANGO_ATHM_WEBHOOK_URL setting
    2. request.build_absolute_uri() if request provided
    3. ValidationError
    """
    if settings.WEBHOOK_URL:
        return settings.WEBHOOK_URL

    if request:
        return request.build_absolute_uri(reverse("django_athm:webhook"))

    raise ValidationError(
        "Set DJANGO_ATHM_WEBHOOK_URL in settings or use admin interface"
    )


def validate_webhook_url(url):
    """Validate webhook URL is HTTPS."""
    validator = URLValidator(schemes=["https"])
    validator(url)
    return url
