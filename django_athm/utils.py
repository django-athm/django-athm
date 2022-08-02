import logging
from abc import ABC, abstractmethod

import httpx

from .constants import API_BASE_URL, ERROR_DICT

logger = logging.getLogger(__name__)


def parse_error_code(error_code):
    return ERROR_DICT.get(error_code, "unknown error")


class BaseHTTPAdapter(ABC):
    client = None

    @abstractmethod
    def get_with_data(self, url, data):
        raise NotImplementedError

    @abstractmethod
    def post(self, url, data):
        raise NotImplementedError


class SyncHTTPAdapter(BaseHTTPAdapter):
    def get_with_data(self, url, data):
        extra = {"url": url}
        logger.debug("[django_athm:get_with_data]", extra=extra)

        with httpx.Client(base_url=API_BASE_URL) as client:
            response = client.request(method="GET", url=url, json=data)
            return response.json()

    def post(self, url, data):
        extra = {"url": url}
        logger.debug("[django_athm:post]", extra=extra)

        with httpx.Client(base_url=API_BASE_URL) as client:
            response = client.post(url, json=data)
            return response.json()


def get_http_adapter():
    return SyncHTTPAdapter()
