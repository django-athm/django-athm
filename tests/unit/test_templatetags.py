import json

import pytest
from django.template import Context, Template

from django_athm.templatetags.django_athm import athm_button


class TestAthmButton:
    def test_returns_required_context_keys(self):
        context = Context({"csrf_token": "test-token"})
        config = {"total": "100.00"}

        result = athm_button(context, config)

        assert "total" in result
        assert "subtotal" in result
        assert "tax" in result
        assert "metadata_1" in result
        assert "metadata_2" in result
        assert "items_json" in result
        assert "success_url" in result
        assert "failure_url" in result
        assert "theme" in result
        assert "language" in result
        assert "initiate_url" in result
        assert "status_url" in result
        assert "authorize_url" in result
        assert "cancel_url" in result
        assert "csrf_token" in result

    def test_total_is_required(self):
        context = Context({})
        config = {}

        with pytest.raises(ValueError, match="must include 'total'"):
            athm_button(context, config)

    def test_total_converted_to_string(self):
        context = Context({})
        config = {"total": 100.50}

        result = athm_button(context, config)

        assert result["total"] == "100.5"

    def test_subtotal_and_tax_converted_to_string(self):
        context = Context({})
        config = {"total": "100.00", "subtotal": 90.00, "tax": 10.00}

        result = athm_button(context, config)

        assert result["subtotal"] == "90.0"
        assert result["tax"] == "10.0"

    def test_subtotal_and_tax_empty_when_not_provided(self):
        context = Context({})
        config = {"total": "100.00"}

        result = athm_button(context, config)

        assert result["subtotal"] == ""
        assert result["tax"] == ""

    def test_metadata_truncated_to_40_chars(self):
        context = Context({})
        long_string = "a" * 50
        config = {
            "total": "100.00",
            "metadata_1": long_string,
            "metadata_2": long_string,
        }

        result = athm_button(context, config)

        assert len(result["metadata_1"]) == 40
        assert len(result["metadata_2"]) == 40

    def test_metadata_empty_when_not_provided(self):
        context = Context({})
        config = {"total": "100.00"}

        result = athm_button(context, config)

        assert result["metadata_1"] == ""
        assert result["metadata_2"] == ""

    def test_items_serialized_to_json(self):
        context = Context({})
        items = [{"name": "Item 1", "price": "10.00"}]
        config = {"total": "10.00", "items": items}

        result = athm_button(context, config)

        assert result["items_json"] == json.dumps(items)

    def test_items_empty_array_when_not_provided(self):
        context = Context({})
        config = {"total": "100.00"}

        result = athm_button(context, config)

        assert result["items_json"] == "[]"

    def test_default_theme_is_btn(self):
        context = Context({})
        config = {"total": "100.00"}

        result = athm_button(context, config)

        assert result["theme"] == "btn"

    def test_custom_theme(self):
        context = Context({})
        config = {"total": "100.00", "theme": "btn-dark"}

        result = athm_button(context, config)

        assert result["theme"] == "btn-dark"

    def test_invalid_theme_falls_back_to_default(self, caplog):
        context = Context({})
        config = {"total": "100.00", "theme": "invalid-theme"}

        result = athm_button(context, config)

        assert result["theme"] == "btn"
        assert "Invalid theme 'invalid-theme'" in caplog.text

    def test_default_language_is_spanish(self):
        context = Context({})
        config = {"total": "100.00"}

        result = athm_button(context, config)

        assert result["language"] == "es"

    def test_custom_language_via_lang(self):
        context = Context({})
        config = {"total": "100.00", "lang": "en"}

        result = athm_button(context, config)

        assert result["language"] == "en"

    def test_invalid_language_falls_back_to_default(self, caplog):
        context = Context({})
        config = {"total": "100.00", "lang": "fr"}

        result = athm_button(context, config)

        assert result["language"] == "es"
        assert "Invalid language 'fr'" in caplog.text

    def test_success_and_failure_urls(self):
        context = Context({})
        config = {
            "total": "100.00",
            "success_url": "/thanks/",
            "failure_url": "/error/",
        }

        result = athm_button(context, config)

        assert result["success_url"] == "/thanks/"
        assert result["failure_url"] == "/error/"

    def test_csrf_token_from_context(self):
        context = Context({"csrf_token": "my-csrf-token"})
        config = {"total": "100.00"}

        result = athm_button(context, config)

        assert result["csrf_token"] == "my-csrf-token"

    def test_csrf_token_empty_when_not_in_context(self):
        context = Context({})
        config = {"total": "100.00"}

        result = athm_button(context, config)

        assert result["csrf_token"] == ""

    def test_urls_are_resolved(self):
        context = Context({})
        config = {"total": "100.00"}

        result = athm_button(context, config)

        assert result["initiate_url"] == "/athm/api/initiate/"
        assert result["status_url"] == "/athm/api/status/"
        assert result["authorize_url"] == "/athm/api/authorize/"
        assert result["cancel_url"] == "/athm/api/cancel/"

    def test_poll_settings(self):
        context = Context({})
        config = {"total": "100.00"}

        result = athm_button(context, config)

        assert result["poll_interval"] == 5
        assert result["max_poll_attempts"] == 60


class TestAthmButtonI18n:
    """Tests for multi-lingual support in the payment button template."""

    @pytest.fixture
    def render_button(self):
        """Helper to render the athm_button template with a given config."""

        def _render(config):
            template = Template("{% load django_athm %}{% athm_button config %}")
            context = Context({"config": config, "csrf_token": "test-token"})
            return template.render(context)

        return _render

    def test_translation_data_attributes_present(self, render_button):
        """All 7 translation data attributes should be present in rendered HTML."""
        html = render_button({"total": "100.00"})

        assert 'data-athm-error-timeout="' in html
        assert 'data-athm-error-cancelled="' in html
        assert 'data-athm-error-expired="' in html
        assert 'data-athm-error-initiate="' in html
        assert 'data-athm-error-status="' in html
        assert 'data-athm-error-authorize="' in html
        assert 'data-athm-confirm-cancel="' in html

    def test_spanish_translations_rendered(self, render_button):
        """Spanish language should render Spanish error messages."""
        html = render_button({"total": "100.00", "lang": "es"})

        # Check Spanish translations are present
        assert "El pago expiró. Por favor intenta de nuevo." in html
        assert "El pago fue cancelado." in html
        assert "Error al iniciar el pago" in html
        assert "Error al verificar el estado" in html
        assert "Error al autorizar el pago" in html
        assert "¿Cancelar este pago?" in html

    def test_english_translations_rendered(self, render_button):
        """English language should render English error messages."""
        html = render_button({"total": "100.00", "lang": "en"})

        # Check English translations are present (original msgid values)
        assert "Payment timed out. Please try again." in html
        assert "Payment was cancelled." in html
        assert "Payment expired. Please try again." in html
        assert "Failed to initiate payment" in html
        assert "Failed to check status" in html
        assert "Failed to authorize payment" in html
        assert "Cancel this payment?" in html

    def test_default_language_is_spanish(self, render_button):
        """Default language should be Spanish."""
        html = render_button({"total": "100.00"})

        # Default (no lang specified) should be Spanish
        assert "El pago fue cancelado." in html
        assert 'data-athm-language="es"' in html

    def test_language_parameter_controls_modal_text(self, render_button):
        """The lang parameter should control the language of modal text."""
        html_es = render_button({"total": "100.00", "lang": "es"})
        html_en = render_button({"total": "100.00", "lang": "en"})

        # Spanish button text
        assert "Continuar" in html_es
        assert "Cancelar" in html_es

        # English button text
        assert "Continue" in html_en
        assert "Cancel" in html_en


class TestAthmButtonTheme:
    """Tests for theme support in the payment button template."""

    @pytest.fixture
    def render_button(self):
        """Helper to render the athm_button template with a given config."""

        def _render(config):
            template = Template("{% load django_athm %}{% athm_button config %}")
            context = Context({"config": config, "csrf_token": "test-token"})
            return template.render(context)

        return _render

    def test_default_theme_applies_btn_theme_class(self, render_button):
        """Default theme should apply athm-theme-btn class to container."""
        html = render_button({"total": "100.00"})

        assert 'class="athm-container athm-theme-btn"' in html
        assert 'class="athm-button athm-btn"' in html

    def test_btn_dark_theme_applies_dark_theme_class(self, render_button):
        """btn-dark theme should apply athm-theme-btn-dark class to container."""
        html = render_button({"total": "100.00", "theme": "btn-dark"})

        assert 'class="athm-container athm-theme-btn-dark"' in html
        assert 'class="athm-button athm-btn-dark"' in html

    def test_btn_light_theme_applies_light_theme_class(self, render_button):
        """btn-light theme should apply athm-theme-btn-light class to container."""
        html = render_button({"total": "100.00", "theme": "btn-light"})

        assert 'class="athm-container athm-theme-btn-light"' in html
        assert 'class="athm-button athm-btn-light"' in html

    def test_modal_buttons_inherit_theme(self, render_button):
        """Modal submit and retry buttons should use the same theme class."""
        html = render_button({"total": "100.00", "theme": "btn-dark"})

        # Submit button in phone step
        assert "data-athm-submit" in html
        assert "athm-btn-dark" in html

        # Retry button in error step
        assert "data-athm-retry" in html

    def test_modal_dialog_has_theme_class(self, render_button):
        """Modal element should have theme class for CSS variable access."""
        html = render_button({"total": "100.00", "theme": "btn-dark"})

        assert 'class="athm-modal athm-theme-btn-dark"' in html
