import json

from django import template
from django.urls import reverse

from django_athm.constants import BUTTON_COLOR_DEFAULT, BUTTON_LANGUAGE_SPANISH

register = template.Library()


@register.inclusion_tag("django_athm/button.html", takes_context=True)
def athm_button(
    context,
    total,
    subtotal=None,
    tax=None,
    metadata_1="",
    metadata_2="",
    items=None,
    success_url="",
    failure_url="",
):
    """
    Render an ATH Móvil payment button with modal.

    Usage:
        {% load athm_tags %}
        {% athm_button total=order.total metadata_1=order.id success_url="/thanks/" %}

    Args:
        total: Payment amount (required, 1.00-1500.00)
        subtotal: Optional subtotal for display
        tax: Optional tax amount
        metadata_1: Custom field (max 40 chars)
        metadata_2: Custom field (max 40 chars)
        items: List of item dicts with name, price, quantity, etc.

        success_url: Redirect URL on successful payment
        failure_url: Redirect URL on failure to capture payment
    """

    # Default texts based on language

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
        "theme": BUTTON_COLOR_DEFAULT,
        "language": BUTTON_LANGUAGE_SPANISH,
        "poll_interval": 5,
        "max_poll_attempts": 60,
        "initiate_url": reverse("django_athm:initiate"),
        "status_url": reverse("django_athm:status"),
        "authorize_url": reverse("django_athm:authorize"),
        "cancel_url": reverse("django_athm:cancel"),
        "csrf_token": csrf_token,
    }
