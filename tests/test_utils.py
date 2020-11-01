from django_athm import constants, utils


def test_parse_error_code():
    assert utils.parse_error_code("3020") == constants.ERROR_DICT["3020"]


class TestHTTPAdapters:
    def test_sync_adapter_get(self):
        pass

    def test_sync_adapter_post(self):
        pass
