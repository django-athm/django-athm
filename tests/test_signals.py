from django.dispatch import receiver
from django.template import Context, Template

from django_athm import signals


class TestTemplateSignals:
    @receiver(signals.athm_cancelled_response)
    @receiver(signals.athm_completed_response)
    @receiver(signals.athm_expired_response)
    @receiver(signals.athm_response_received)
    def signal_callback(sender, **_kwargs):
        assert sender == "django_athm"

    def test_cancelled_signal(self):
        template_to_render = Template(
            "{% load athm_response_signal %} {% athm_response_signal 'cancelled' %}"
        )
        template_to_render.render(context=Context())

    def test_expired_signal(self):
        template_to_render = Template(
            "{% load athm_response_signal %} {% athm_response_signal 'expired' %}"
        )
        template_to_render.render(context=Context())

    def test_completed_signal(self):
        template_to_render = Template(
            "{% load athm_response_signal %} {% athm_response_signal 'completed' %}"
        )
        template_to_render.render(context=Context())
