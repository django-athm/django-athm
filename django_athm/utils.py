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

    def post(self, url, data):
        raise NotImplementedError


class DummyHTTPAdapter(BaseHTTPAdapter):
    def get(self, url):
        logger.debug(f"[DummyHTTPAdapter:get] URL: {url}")

        if url == STATUS_URL:
            return {}

    def post(self, url, data):
        logger.debug(f"[DummyHTTPAdapter:post] URL: {url}")

        if url == REFUND_URL:
            return {
                "refundStatus": "completed",
                "referenceNumber": "test-reference-number",
                "date": "2020-01-25 19:05:53.0",
                "refundedAmount": "1.00",
                "total": "1.00",
                "tax": "0.00",
                "subtotal": "0.00",
                "metadata1": None,
                "metadata2": None,
                "items": '[{"name":"First Item","description":"This is a description.","quantity":"1","price":"1.00","tax":"1.00","metadata":"metadata test"}]',
            }


class AsyncHTTPAdapter(BaseHTTPAdapter):
    pass


class SyncHTTPAdapter(BaseHTTPAdapter):
    client = httpx.Client(base_url=API_BASE_URL)

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
