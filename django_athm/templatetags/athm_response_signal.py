import logging

from django import template

from django_athm.constants import TransactionStatus
from django_athm.signals import (
    athm_cancelled_response,
    athm_completed_response,
    athm_expired_response,
    athm_response_received,
)

register = template.Library()

logger = logging.getLogger(__name__)


@register.simple_tag
def athm_response_signal(status):
    logger.debug("[django_athm:athm_response_signal]", extra={"status": status})

    if status == TransactionStatus.expired.value:
        athm_expired_response.send(sender="django_athm")
    elif status == TransactionStatus.cancelled.value:
        athm_cancelled_response.send(sender="django_athm")
    elif status == TransactionStatus.completed.value:
        athm_completed_response.send(sender="django_athm")

    # Send a general signal
    athm_response_received.send(sender="django_athm")
