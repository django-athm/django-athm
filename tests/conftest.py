import pytest
import respx
from httpx import Response

from django_athm.constants import (
    API_BASE_URL,
    CANCEL_PAYMENT_URL,
    FIND_PAYMENT_URL,
    REFUND_URL,
    REPORT_URL,
    SEARCH_URL,
)
from django_athm.utils import SyncHTTPAdapter


@pytest.fixture()
def mock_http_adapter_get_with_data(mocker):
    return mocker.patch.object(SyncHTTPAdapter, "get_with_data")


@pytest.fixture()
def mock_http_adapter_post(mocker):
    return mocker.patch.object(SyncHTTPAdapter, "post")


@pytest.fixture
def mock_httpx():
    with respx.mock(base_url=API_BASE_URL, assert_all_called=False) as respx_mock:
        get_with_data_route = respx_mock.get(REPORT_URL, name="get_with_data")
        get_with_data_route.return_value = Response(200, json={"mocked": True})

        post_status_route = respx_mock.post(SEARCH_URL, name="post_status", json={})
        post_status_route.return_value = Response(200, json={"mocked": True})

        post_refund_route = respx_mock.post(REFUND_URL, name="post_refund", json={})
        post_refund_route.return_value = Response(200, json={"mocked": True})

        # v4 API endpoints
        post_find_payment = respx_mock.post(
            FIND_PAYMENT_URL, name="post_find_payment", json={}
        )
        post_find_payment.return_value = Response(200, json={"mocked": True})

        post_cancel_payment = respx_mock.post(
            CANCEL_PAYMENT_URL, name="post_cancel_payment", json={}
        )
        post_cancel_payment.return_value = Response(200, json={"mocked": True})

        yield respx_mock
