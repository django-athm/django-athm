# from contextlib import AbstractContextManager

import logging

import httpx
from django.conf import settings

from .constants import API_BASE_URL, ERROR_DICT, REFUND_URL, STATUS_URL

logger = logging.getLogger(__name__)


def parse_error_code(error_code):
    return ERROR_DICT.get(error_code, "unknown error")


class BaseHTTPAdapter:
    client = None

    def get(self, url):
        raise NotImplementedError

    def get_with_data(self, url, data):
        raise NotImplementedError

    def post(self, url, data):
        raise NotImplementedError


class DummyHTTPAdapter(BaseHTTPAdapter):
    def get_with_data(self, url, data):
        return [
            {
                "transactionType": "refund",
                "referenceNumber": "212831546-7638e92vjhsbjbsdkjqbjkbqdq",
                "date": "2019-06-06 17:12:02.0",
                "refundedAmount": "1.00",
                "total": "1.00",
                "tax": "1.00",
                "subtotal": "1.00",
                "metadata1": "metadata1 test",
                "metadata2": "metadata2 test",
                "items": [
                    {
                        "name": "First Item",
                        "description": "This is a description.",
                        "quantity": "1",
                        "price": "1.00",
                        "tax": "1.00",
                        "metadata": "metadata test",
                    },
                    {
                        "name": "Second Item",
                        "description": "This is another description.",
                        "quantity": "1",
                        "price": "1.00",
                        "tax": "1.00",
                        "metadata": "metadata test",
                    },
                ],
            },
            {
                "transactionType": "payment",
                "status": "completed",
                "referenceNumber": "212831546-402894d56b240610016b2e6c78a6003a",
                "date": "2019-06-06 16:12:02.0",
                "refundedAmount": "0.00",
                "total": "5.00",
                "tax": "1.00",
                "subtotal": "4.00",
                "metadata1": "metadata1 test",
                "metadata2": "metadata2 test",
                "items": [
                    {
                        "name": "First Item",
                        "description": "This is a description.",
                        "quantity": "1",
                        "price": "1.00",
                        "tax": "1.00",
                        "metadata": "metadata test",
                    },
                    {
                        "name": "Second Item",
                        "description": "This is another description.",
                        "quantity": "1",
                        "price": "1.00",
                        "tax": "1.00",
                        "metadata": "metadata test",
                    },
                ],
            },
        ]

    def get(self, url):
        logger.debug(f"[DummyHTTPAdapter:get] URL: {url}")

        if url == STATUS_URL:
            return {"url": url}

    def post(self, url, data):
        logger.debug(f"[DummyHTTPAdapter:post] URL: {url}")

        if url == REFUND_URL:
            # Force fail (for testing)
            if data["referenceNumber"] == "error":
                return {
                    "errorCode": "5010",
                    "description": "Transaction does not exist",
                }

            return {
                "refundStatus": "completed",
                "refundedAmount": data["amount"],
                "data": data,
            }


class AsyncHTTPAdapter(BaseHTTPAdapter):
    pass


class SyncHTTPAdapter(BaseHTTPAdapter):
    client = httpx.Client(base_url=API_BASE_URL)

    def get_with_data(self, url, data):
        logger.debug(f"[SyncHTTPAdapter:get_with_data] URL: {url}")
        with self.client as client:
            response = client.request(method="GET", url=url, json=data)
            return response.json()

    def get(self, url):
        logger.debug(f"[SyncHTTPAdapter:get] URL: {url}")

        with self.client as client:
            response = client.get(url)
            return response.json()

    def post(self, url, data):
        logger.debug(f"[SyncHTTPAdapter:post] URL: {url}")

        with self.client as client:
            response = client.post(url, json=data)
            return response.json()


def get_http_adapter():
    if settings.DEBUG:
        return DummyHTTPAdapter()

    # TODO: If async is supported, use the AsyncHTTPAdapter
    return SyncHTTPAdapter()
