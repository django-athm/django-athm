import pytest
from django.core.exceptions import ValidationError

from django_athm.utils import get_webhook_url, validate_webhook_url

pytestmark = pytest.mark.django_db


class TestGetWebhookUrl:
    def test_get_webhook_url_from_setting(self, settings):
        """Test URL resolution from DJANGO_ATHM_WEBHOOK_URL setting."""
        settings.DJANGO_ATHM_WEBHOOK_URL = "https://example.com/athm/webhook/"

        url = get_webhook_url()

        assert url == "https://example.com/athm/webhook/"

    def test_get_webhook_url_from_request(self, rf):
        """Test URL resolution from request.build_absolute_uri()."""
        request = rf.get("/", HTTP_HOST="myapp.com")

        url = get_webhook_url(request=request)

        assert "myapp.com" in url
        assert "/athm/webhook/" in url

    def test_get_webhook_url_fails_without_config(self, settings):
        """Test that ValidationError is raised when no configuration is available."""
        # Ensure setting is not configured
        if hasattr(settings, "DJANGO_ATHM_WEBHOOK_URL"):
            delattr(settings, "DJANGO_ATHM_WEBHOOK_URL")

        with pytest.raises(ValidationError) as exc_info:
            get_webhook_url(request=None)

        assert "Set DJANGO_ATHM_WEBHOOK_URL" in str(exc_info.value)

    def test_setting_takes_priority_over_request(self, rf, settings):
        """Test that setting takes priority over request."""
        settings.DJANGO_ATHM_WEBHOOK_URL = "https://setting.com/webhook/"
        request = rf.get("/", HTTP_HOST="request.com")

        url = get_webhook_url(request=request)

        assert url == "https://setting.com/webhook/"


class TestValidateWebhookUrl:
    def test_validate_webhook_url_requires_https(self):
        """Test that non-HTTPS URLs are rejected."""
        with pytest.raises(ValidationError):
            validate_webhook_url("http://example.com/webhook/")

    def test_validate_webhook_url_accepts_https(self):
        """Test that HTTPS URLs are accepted."""
        url = validate_webhook_url("https://example.com/webhook/")

        assert url == "https://example.com/webhook/"

    def test_validate_webhook_url_rejects_invalid_urls(self):
        """Test that invalid URLs are rejected."""
        with pytest.raises(ValidationError):
            validate_webhook_url("not-a-url")

    def test_validate_webhook_url_rejects_missing_scheme(self):
        """Test that URLs without scheme are rejected."""
        with pytest.raises(ValidationError):
            validate_webhook_url("example.com/webhook/")
