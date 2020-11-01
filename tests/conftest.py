import pytest

from django_athm.utils import SyncHTTPAdapter


@pytest.fixture(autouse=True)
def mock_http_adapter_get_with_data(mocker):
    return mocker.patch.object(SyncHTTPAdapter, "get_with_data")


@pytest.fixture(autouse=True)
def mock_http_adapter_post(mocker):
    return mocker.patch.object(SyncHTTPAdapter, "post")
