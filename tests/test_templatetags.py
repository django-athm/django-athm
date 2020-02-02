from django.dispatch import receiver
from django.template import Context, Template
from pytest_django.asserts import assertTemplateUsed

from django_athm import signals


class TestTemplateSignals:
    @receiver(signals.athm_cancelled_response)
    @receiver(signals.athm_completed_response)
    @receiver(signals.athm_expired_response)
    @receiver(signals.athm_response_received)
    def signal_callback(sender, **kwargs):
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


class TestTemplateButton:
    def test_athm_button_template(self):
        template_to_render = Template(
            """
            {% load django_athm %}
            {% athm_button ATHM_CONFIG %}
            """
        )

        with assertTemplateUsed("athm_button.html"):
            rendered_template = template_to_render.render(
                context=Context(
                    {
                        "ATHM_CONFIG": {
                            "total": 25.0,
                            "subtotal": 24.0,
                            "tax": 1.0,
                            "items": [
                                {
                                    "name": "First Item",
                                    "description": "This is a description.",
                                    "quantity": "1",
                                    "price": "24.00",
                                    "tax": "1.00",
                                    "metadata": "metadata test",
                                }
                            ],
                        }
                    }
                )
            )

        assert '<div id="ATHMovil_Checkout_Button"></div>' in rendered_template
