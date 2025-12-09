import json

import pytest
from django.template import Context

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

    def test_custom_language_via_language(self):
        context = Context({})
        config = {"total": "100.00", "language": "en"}

        result = athm_button(context, config)

        assert result["language"] == "en"

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
