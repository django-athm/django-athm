import logging

from django import template

from .. import constants, signals

register = template.Library()

logger = logging.getLogger(__name__)


@register.simple_tag
def athm_response_signal(status):
    logger.debug("[templatetags:athm_response_signal]")

    if status == constants.EXPIRED_STATUS:
        signals.athm_expired_response.send(sender="django_athm")
    elif status == constants.CANCELLED_STATUS:
        signals.athm_cancelled_response.send(sender="django_athm")
    elif status == constants.COMPLETED_STATUS:
        signals.athm_completed_response.send(sender="django_athm")

    # Send a general signal
    signals.athm_response_received.send(sender="django_athm")
