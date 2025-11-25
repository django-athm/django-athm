import httpx
import pytest
import respx
from httpx import Response

from django_athm import constants, utils


def test_parse_error_code():
    """Test error code parsing returns correct message."""
    assert utils.parse_error_code("3020") == constants.ERROR_DICT["3020"]


def test_parse_error_code_unknown():
    """Test error code parsing returns 'unknown error' for unknown codes."""
    assert utils.parse_error_code("9999") == "unknown error"


class TestSyncHTTPAdapter:
    def test_adapter_get_with_data(self, mock_httpx):
        """Test successful GET request with data."""
        adapter = utils.SyncHTTPAdapter()

        response = adapter.get_with_data(constants.REPORT_URL, data={})

        assert response["mocked"]
        assert mock_httpx.routes["get_with_data"].called

    def test_adapter_post(self, mock_httpx):
        """Test successful POST request."""
        adapter = utils.SyncHTTPAdapter()

        response = adapter.post(constants.REFUND_URL, data={})

        assert response["mocked"]
        assert mock_httpx.routes["post_refund"].called

    def test_adapter_custom_timeout(self):
        """Test adapter accepts custom timeout."""
        adapter = utils.SyncHTTPAdapter(timeout=60.0)
        assert adapter.timeout == 60.0
        adapter.client.close()

    def test_adapter_default_timeout(self):
        """Test adapter has default timeout of 30 seconds."""
        adapter = utils.SyncHTTPAdapter()
        assert adapter.timeout == 30.0
        adapter.client.close()


class TestSyncHTTPAdapterErrorHandling:
    """Tests for HTTP adapter error handling."""

    @respx.mock
    def test_get_timeout_exception(self):
        """Test GET request handles timeout exception."""
        respx.get(constants.REPORT_URL).mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        adapter = utils.SyncHTTPAdapter()
        with pytest.raises(httpx.TimeoutException):
            adapter.get_with_data(constants.REPORT_URL, data={})
        adapter.client.close()

    @respx.mock
    def test_post_timeout_exception(self):
        """Test POST request handles timeout exception."""
        respx.post(constants.REFUND_URL).mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        adapter = utils.SyncHTTPAdapter()
        with pytest.raises(httpx.TimeoutException):
            adapter.post(constants.REFUND_URL, data={})
        adapter.client.close()

    @respx.mock
    def test_get_connection_error(self):
        """Test GET request handles connection error."""
        respx.get(constants.REPORT_URL).mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        adapter = utils.SyncHTTPAdapter()
        with pytest.raises(httpx.ConnectError):
            adapter.get_with_data(constants.REPORT_URL, data={})
        adapter.client.close()

    @respx.mock
    def test_post_connection_error(self):
        """Test POST request handles connection error."""
        respx.post(constants.REFUND_URL).mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        adapter = utils.SyncHTTPAdapter()
        with pytest.raises(httpx.ConnectError):
            adapter.post(constants.REFUND_URL, data={})
        adapter.client.close()

    @respx.mock
    def test_get_http_400_with_json_error(self):
        """Test GET request returns JSON body on HTTP 400 error."""
        respx.get(constants.REPORT_URL).mock(
            return_value=Response(
                400, json={"errorCode": "3010", "description": "publicToken is invalid"}
            )
        )

        adapter = utils.SyncHTTPAdapter()
        response = adapter.get_with_data(constants.REPORT_URL, data={})
        assert response["errorCode"] == "3010"
        adapter.client.close()

    @respx.mock
    def test_post_http_400_with_json_error(self):
        """Test POST request returns JSON body on HTTP 400 error."""
        respx.post(constants.REFUND_URL).mock(
            return_value=Response(
                400, json={"errorCode": "7020", "description": "amount is invalid"}
            )
        )

        adapter = utils.SyncHTTPAdapter()
        response = adapter.post(constants.REFUND_URL, data={})
        assert response["errorCode"] == "7020"
        adapter.client.close()

    @respx.mock
    def test_get_http_401_unauthorized(self):
        """Test GET request returns JSON body on HTTP 401 error."""
        respx.get(constants.REPORT_URL).mock(
            return_value=Response(
                401,
                json={"errorCode": "3040", "description": "privateToken is invalid"},
            )
        )

        adapter = utils.SyncHTTPAdapter()
        response = adapter.get_with_data(constants.REPORT_URL, data={})
        assert response["errorCode"] == "3040"
        adapter.client.close()

    @respx.mock
    def test_post_http_500_with_json_error(self):
        """Test POST request returns JSON body on HTTP 500 error."""
        respx.post(constants.REFUND_URL).mock(
            return_value=Response(
                500,
                json={"errorCode": "7040", "description": "error completing refund"},
            )
        )

        adapter = utils.SyncHTTPAdapter()
        response = adapter.post(constants.REFUND_URL, data={})
        assert response["errorCode"] == "7040"
        adapter.client.close()

    @respx.mock
    def test_get_http_error_non_json_response(self):
        """Test GET request raises JSONDecodeError on HTTP error with non-JSON response."""
        import json

        respx.get(constants.REPORT_URL).mock(
            return_value=Response(500, text="Internal Server Error")
        )

        adapter = utils.SyncHTTPAdapter()
        with pytest.raises(json.JSONDecodeError):
            adapter.get_with_data(constants.REPORT_URL, data={})
        adapter.client.close()

    @respx.mock
    def test_post_http_error_non_json_response(self):
        """Test POST request raises JSONDecodeError on HTTP error with non-JSON response."""
        import json

        respx.post(constants.REFUND_URL).mock(
            return_value=Response(500, text="Internal Server Error")
        )

        adapter = utils.SyncHTTPAdapter()
        with pytest.raises(json.JSONDecodeError):
            adapter.post(constants.REFUND_URL, data={})
        adapter.client.close()

    @respx.mock
    def test_get_successful_json_response(self):
        """Test GET request parses successful JSON response."""
        respx.get(constants.REPORT_URL).mock(
            return_value=Response(200, json={"transactions": [], "total": 0})
        )

        adapter = utils.SyncHTTPAdapter()
        response = adapter.get_with_data(constants.REPORT_URL, data={})
        assert response["total"] == 0
        assert response["transactions"] == []
        adapter.client.close()

    @respx.mock
    def test_post_successful_json_response(self):
        """Test POST request parses successful JSON response."""
        respx.post(constants.REFUND_URL).mock(
            return_value=Response(
                200, json={"refundStatus": "COMPLETED", "refundedAmount": "25.50"}
            )
        )

        adapter = utils.SyncHTTPAdapter()
        response = adapter.post(constants.REFUND_URL, data={})
        assert response["refundStatus"] == "COMPLETED"
        adapter.client.close()


class TestGetHttpAdapter:
    """Tests for the get_http_adapter factory function."""

    def test_returns_sync_adapter(self):
        """Test get_http_adapter returns SyncHTTPAdapter instance."""
        adapter = utils.get_http_adapter()
        assert isinstance(adapter, utils.SyncHTTPAdapter)
        adapter.client.close()
