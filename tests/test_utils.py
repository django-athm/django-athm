from django_athm import constants, utils


def test_parse_error_code():
    assert utils.parse_error_code("3020") == constants.ERROR_DICT["3020"]


class TestHTTPAdapters:
    def test_get_http_adapter_with_debug(self, settings):
        settings.DEBUG = True
        adapter = utils.get_http_adapter()
        isinstance(adapter, utils.DummyHTTPAdapter)

    def test_get_http_adapter_without_debug(self, settings):
        settings.DEBUG = False
        adapter = utils.get_http_adapter()
        isinstance(adapter, utils.SyncHTTPAdapter)

    def test_dummy_adapter_post(self):
        pass

    def test_dummy_adapter_get(self):
        pass

    def test_sync_adapter_post(self):
        pass

    def test_sync_adapter_get(self):
        pass
