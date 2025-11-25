from django.template import Context, Template


class TestTemplateButton:
    def test_athm_button_template(self):
        template_to_render = Template(
            """
            {% load django_athm %}
            {% athm_button ATHM_CONFIG %}
            """
        )

        rendered_template = template_to_render.render(
            context=Context(
                {
                    "ATHM_CONFIG": {
                        "total": 25.0,
                        "subtotal": 24.0,
                        "tax": 1.0,
                        "metadata_1": "Test metadata 1",
                        "metadata_2": "Test metadata 2",
                        "phone_number": 7871234567,
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

        assert '<div id="ATHMovil_Checkout_Button_payment"' in rendered_template

    def test_athm_button_template_without_settings(self, settings):
        del settings.DJANGO_ATHM_PUBLIC_TOKEN
        del settings.DJANGO_ATHM_PRIVATE_TOKEN

        template_to_render = Template(
            """
            {% load django_athm %}
            {% athm_button ATHM_CONFIG %}
            """
        )

        rendered_template = template_to_render.render(
            context=Context(
                {
                    "ATHM_CONFIG": {
                        "total": 25.0,
                        "subtotal": 24.0,
                        "tax": 1.0,
                        "metadata_1": "Test metadata 1",
                        "metadata_2": "Test metadata 2",
                        "phone_number": 7871234567,
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

        assert '<div id="ATHMovil_Checkout_Button_payment"' in rendered_template
