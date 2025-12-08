from io import StringIO
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


class TestInstallWebhookCommand:
    def test_success(self, mocker):
        mock_client = Mock()
        mocker.patch(
            "django_athm.management.commands.install_webhook.PaymentService.get_client",
            return_value=mock_client,
        )

        out = StringIO()
        call_command("install_webhook", "https://example.com/webhook/", stdout=out)

        mock_client.subscribe_webhook.assert_called_once_with(
            listener_url="https://example.com/webhook/"
        )
        assert "Webhook installed" in out.getvalue()

    def test_http_url_rejected(self):
        with pytest.raises(CommandError) as exc_info:
            call_command("install_webhook", "http://example.com/webhook/")

        assert "HTTPS" in str(exc_info.value)

    def test_invalid_url_rejected(self):
        with pytest.raises(CommandError) as exc_info:
            call_command("install_webhook", "not-a-valid-url")

        assert "HTTPS" in str(exc_info.value)

    def test_api_error_handled(self, mocker):
        mock_client = Mock()
        mock_client.subscribe_webhook.side_effect = Exception("API Error")
        mocker.patch(
            "django_athm.management.commands.install_webhook.PaymentService.get_client",
            return_value=mock_client,
        )

        with pytest.raises(CommandError) as exc_info:
            call_command("install_webhook", "https://example.com/webhook/")

        assert "Failed to install webhook" in str(exc_info.value)
        assert "API Error" in str(exc_info.value)
