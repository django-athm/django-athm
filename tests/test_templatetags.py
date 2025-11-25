import pytest
from django.template import Context, Template

from django_athm.constants import BUTTON_COLOR_DEFAULT, BUTTON_LANGUAGE_SPANISH
from django_athm.templatetags.django_athm import athm_button


def get_valid_config(**overrides):
    """Helper to create a valid ATHM config with optional overrides."""
    config = {
        "total": 25.0,
        "subtotal": 24.0,
        "tax": 1.0,
        "metadata_1": "Test metadata 1",
        "metadata_2": "Test metadata 2",
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
    config.update(overrides)
    return config


class TestTemplateButton:
    def test_athm_button_template(self):
        """Test successful button rendering with valid config."""
        template_to_render = Template(
            """
            {% load django_athm %}
            {% athm_button ATHM_CONFIG %}
            """
        )

        rendered_template = template_to_render.render(
            context=Context({"ATHM_CONFIG": get_valid_config()})
        )

        assert '<div id="ATHMovil_Checkout_Button_payment"' in rendered_template

    def test_athm_button_template_without_settings(self, settings):
        """Test button renders without global token settings."""
        del settings.DJANGO_ATHM_PUBLIC_TOKEN
        del settings.DJANGO_ATHM_PRIVATE_TOKEN

        template_to_render = Template(
            """
            {% load django_athm %}
            {% athm_button ATHM_CONFIG %}
            """
        )

        rendered_template = template_to_render.render(
            context=Context({"ATHM_CONFIG": get_valid_config()})
        )

        assert '<div id="ATHMovil_Checkout_Button_payment"' in rendered_template


class TestTemplateButtonAmountValidation:
    """Tests for total amount validation (must be $1.00 - $1,500.00)."""

    def test_total_below_minimum_raises_error(self):
        """Test total amount below $1.00 raises ValueError."""
        config = get_valid_config(total=0.99)
        with pytest.raises(ValueError, match="must be between"):
            athm_button(config)

    def test_total_at_minimum_passes(self):
        """Test total amount exactly $1.00 passes validation."""
        config = get_valid_config(total=1.00)
        result = athm_button(config)
        assert result["total"] == 1.00

    def test_total_at_maximum_passes(self):
        """Test total amount exactly $1,500.00 passes validation."""
        config = get_valid_config(total=1500.00)
        result = athm_button(config)
        assert result["total"] == 1500.00

    def test_total_above_maximum_raises_error(self):
        """Test total amount above $1,500.00 raises ValueError."""
        config = get_valid_config(total=1500.01)
        with pytest.raises(ValueError, match="must be between"):
            athm_button(config)

    def test_total_zero_raises_error(self):
        """Test zero total raises ValueError."""
        config = get_valid_config(total=0)
        with pytest.raises(ValueError, match="must be between"):
            athm_button(config)

    def test_total_negative_raises_error(self):
        """Test negative total raises ValueError."""
        config = get_valid_config(total=-10.00)
        with pytest.raises(ValueError, match="must be between"):
            athm_button(config)


class TestTemplateButtonMetadataValidation:
    """Tests for metadata field validation."""

    def test_missing_metadata_1_raises_error(self):
        """Test missing metadata_1 raises ValueError."""
        config = get_valid_config()
        del config["metadata_1"]
        with pytest.raises(ValueError, match="metadata_1 is required"):
            athm_button(config)

    def test_empty_metadata_1_raises_error(self):
        """Test empty metadata_1 raises ValueError."""
        config = get_valid_config(metadata_1="")
        with pytest.raises(ValueError, match="metadata_1 is required"):
            athm_button(config)

    def test_missing_metadata_2_raises_error(self):
        """Test missing metadata_2 raises ValueError."""
        config = get_valid_config()
        del config["metadata_2"]
        with pytest.raises(ValueError, match="metadata_2 is required"):
            athm_button(config)

    def test_empty_metadata_2_raises_error(self):
        """Test empty metadata_2 raises ValueError."""
        config = get_valid_config(metadata_2="")
        with pytest.raises(ValueError, match="metadata_2 is required"):
            athm_button(config)

    def test_metadata_1_truncated_at_40_chars(self, caplog):
        """Test metadata_1 longer than 40 chars is truncated."""
        long_metadata = "A" * 50
        config = get_valid_config(metadata_1=long_metadata)
        result = athm_button(config)
        assert result["metadata1"] == "A" * 40
        assert "truncating" in caplog.text

    def test_metadata_2_truncated_at_40_chars(self, caplog):
        """Test metadata_2 longer than 40 chars is truncated."""
        long_metadata = "B" * 50
        config = get_valid_config(metadata_2=long_metadata)
        result = athm_button(config)
        assert result["metadata2"] == "B" * 40
        assert "truncating" in caplog.text

    def test_metadata_exactly_40_chars_not_truncated(self, caplog):
        """Test metadata exactly 40 chars is not truncated."""
        metadata = "C" * 40
        config = get_valid_config(metadata_1=metadata, metadata_2=metadata)
        result = athm_button(config)
        assert result["metadata1"] == metadata
        assert result["metadata2"] == metadata
        assert "truncating" not in caplog.text


class TestATHMovilV4APIBugWorkarounds:
    """Tests for ATH Movil v4 API bug workarounds.

    ATH Movil's v4 API has several known bugs:
    - phone_number: Causes BTRA_0041 error if provided
    - theme: Only "btn" works (btn-light, btn-dark are broken)
    - language: Only "es" works (en is broken)
    """

    def test_phone_number_ignored_with_warning(self, caplog):
        """Test phone_number is ignored and logs warning."""
        config = get_valid_config(phone_number=7871234567)
        result = athm_button(config)
        # phone_number should NOT be in result
        assert "phone_number" not in result
        assert "BTRA_0041" in caplog.text

    def test_phone_number_string_ignored_with_warning(self, caplog):
        """Test string phone_number is also ignored."""
        config = get_valid_config(phone_number="7871234567")
        result = athm_button(config)
        assert "phone_number" not in result
        assert "BTRA_0041" in caplog.text

    def test_no_warning_when_phone_number_not_provided(self, caplog):
        """Test no warning when phone_number is not in config."""
        config = get_valid_config()
        athm_button(config)
        assert "BTRA_0041" not in caplog.text

    def test_theme_hardcoded_to_btn(self):
        """Test theme is always 'btn' regardless of config."""
        config = get_valid_config(theme="btn-dark")
        result = athm_button(config)
        assert result["theme"] == BUTTON_COLOR_DEFAULT

    def test_theme_warning_when_not_default(self, caplog):
        """Test warning logged when theme is not 'btn'."""
        config = get_valid_config(theme="btn-light")
        athm_button(config)
        assert "theme 'btn-light' is ignored" in caplog.text

    def test_no_theme_warning_when_default(self, caplog):
        """Test no warning when theme is 'btn' or not provided."""
        config = get_valid_config()
        athm_button(config)
        assert "theme" not in caplog.text.lower() or "ignored" not in caplog.text

    def test_language_hardcoded_to_es(self):
        """Test language is always 'es' regardless of config."""
        config = get_valid_config(language="en")
        result = athm_button(config)
        assert result["lang"] == BUTTON_LANGUAGE_SPANISH

    def test_language_warning_when_not_spanish(self, caplog):
        """Test warning logged when language is not 'es'."""
        config = get_valid_config(language="en")
        athm_button(config)
        assert "language 'en' is ignored" in caplog.text

    def test_no_language_warning_when_spanish(self, caplog):
        """Test no warning when language is 'es' or not provided."""
        config = get_valid_config()
        athm_button(config)
        assert "language" not in caplog.text.lower() or "ignored" not in caplog.text


class TestTemplateButtonTimeoutValidation:
    """Tests for timeout validation (120-600 seconds)."""

    def test_timeout_below_minimum_uses_default(self, caplog):
        """Test timeout below 120 logs warning and uses 600."""
        config = get_valid_config(timeout=119)
        result = athm_button(config)
        assert result["timeout"] == 600
        assert "outside recommended range" in caplog.text

    def test_timeout_at_minimum_passes(self, caplog):
        """Test timeout exactly 120 passes validation."""
        config = get_valid_config(timeout=120)
        result = athm_button(config)
        assert result["timeout"] == 120
        assert "outside recommended range" not in caplog.text

    def test_timeout_at_maximum_passes(self, caplog):
        """Test timeout exactly 600 passes validation."""
        config = get_valid_config(timeout=600)
        result = athm_button(config)
        assert result["timeout"] == 600
        assert "outside recommended range" not in caplog.text

    def test_timeout_above_maximum_uses_default(self, caplog):
        """Test timeout above 600 logs warning and uses 600."""
        config = get_valid_config(timeout=601)
        result = athm_button(config)
        assert result["timeout"] == 600
        assert "outside recommended range" in caplog.text

    def test_default_timeout_is_600(self, caplog):
        """Test default timeout is 600 seconds."""
        config = get_valid_config()
        if "timeout" in config:
            del config["timeout"]
        result = athm_button(config)
        assert result["timeout"] == 600
        assert "outside recommended range" not in caplog.text


class TestTemplateButtonConfigOutput:
    """Tests for correct output configuration."""

    def test_output_has_env_production(self):
        """Test output env is always 'production'."""
        config = get_valid_config()
        result = athm_button(config)
        assert result["env"] == "production"

    def test_output_has_public_token(self, settings):
        """Test output includes public token from settings."""
        settings.DJANGO_ATHM_PUBLIC_TOKEN = "test-public-token"
        config = get_valid_config()
        result = athm_button(config)
        assert result["publicToken"] == "test-public-token"

    def test_output_uses_config_public_token(self):
        """Test output uses public token from config if provided."""
        config = get_valid_config(public_token="config-token")
        result = athm_button(config)
        assert result["publicToken"] == "config-token"

    def test_output_has_all_required_fields(self):
        """Test output has all required ATH Movil fields."""
        config = get_valid_config()
        result = athm_button(config)
        required_fields = [
            "env",
            "publicToken",
            "lang",
            "timeout",
            "theme",
            "total",
            "subtotal",
            "items",
            "tax",
            "metadata1",
            "metadata2",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
        # phone_number should NOT be in output due to ATH Movil bug
        assert "phone_number" not in result
