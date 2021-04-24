from django_athm import constants, utils


def test_parse_error_code():
    assert utils.parse_error_code("3020") == constants.ERROR_DICT["3020"]


class TestSyncHTTPAdapter:
    def test_adapter_get_with_data(self, mock_httpx):
        adapter = utils.SyncHTTPAdapter()

        response = adapter.get_with_data(constants.LIST_URL, data={})

        assert response["mocked"]
        assert mock_httpx.routes["get_with_data"].called

    def test_adapter_post(self, mock_httpx):
        adapter = utils.SyncHTTPAdapter()

        response = adapter.post(constants.REFUND_URL, data={})

        assert response["mocked"]
        assert mock_httpx.routes["post_refund"].called
