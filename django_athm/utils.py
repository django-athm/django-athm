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
            return {"url": url}

    def post(self, url, data):
        logger.debug(f"[DummyHTTPAdapter:post] URL: {url}")

        if url == REFUND_URL:
            return {
                "refundStatus": "completed",
                "refundedAmount": data["amount"],
                "data": data,
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
