import logging

import httpx

from .constants import API_BASE_URL, ERROR_DICT

logger = logging.getLogger(__name__)


def parse_error_code(error_code):
    return ERROR_DICT.get(error_code, "unknown error")


class SyncHTTPAdapter:
    """HTTP adapter with connection pooling for better performance."""

    def __init__(self):
        self.client = httpx.Client(base_url=API_BASE_URL)

    def get_with_data(self, url, data):
        extra = {"url": url}
        logger.debug("[django_athm:get_with_data]", extra=extra)

        response = self.client.request(method="GET", url=url, json=data)
        return response.json()

    def post(self, url, data):
        extra = {"url": url}
        logger.debug("[django_athm:post]", extra=extra)

        response = self.client.post(url, json=data)
        return response.json()

    def close(self):
        """Close the HTTP client connection."""
        self.client.close()


# Module-level singleton instance for connection pooling
_http_adapter = None


def get_http_adapter():
    """Get or create the singleton HTTP adapter instance."""
    global _http_adapter
    if _http_adapter is None:
        _http_adapter = SyncHTTPAdapter()
    return _http_adapter
