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
    """
    Modern synchronous HTTP adapter with connection pooling, error handling,
    and proper timeout management.
    """

    def __init__(self, timeout: float = 30.0):
        """
        Initialize adapter with connection pooling.

        Args:
            timeout: Request timeout in seconds (default: 30)
        """
        self.timeout = timeout
        # Reuse client for connection pooling
        self.client = httpx.Client(
            base_url=API_BASE_URL,
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    def __del__(self):
        """Clean up HTTP client on deletion."""
        if hasattr(self, "client"):
            self.client.close()

    def get_with_data(self, url, data):
        extra = {"url": url, "method": "GET"}
        logger.debug("[django_athm:get_with_data]", extra=extra)

        try:
            response = self.client.request(method="GET", url=url, json=data)
            response.raise_for_status()

            logger.debug(
                "[django_athm:response]",
                extra={"status_code": response.status_code, "url": url},
            )

            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                "[django_athm:http_error]",
                extra={
                    "status_code": e.response.status_code,
                    "url": url,
                    "error": str(e),
                },
            )
            # Try to return JSON error response if available
            try:
                return e.response.json()
            except Exception:
                raise

        except httpx.TimeoutException:
            logger.error(
                "[django_athm:timeout]", extra={"url": url, "timeout": self.timeout}
            )
            raise

        except Exception as e:
            logger.error(
                "[django_athm:request_error]", extra={"url": url, "error": str(e)}
            )
            raise

    def post(self, url, data):
        extra = {"url": url, "method": "POST"}
        logger.debug("[django_athm:post]", extra=extra)

        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()

            logger.debug(
                "[django_athm:response]",
                extra={"status_code": response.status_code, "url": url},
            )

            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                "[django_athm:http_error]",
                extra={
                    "status_code": e.response.status_code,
                    "url": url,
                    "error": str(e),
                },
            )
            # Try to return JSON error response if available
            try:
                return e.response.json()
            except Exception:
                raise

        except httpx.TimeoutException:
            logger.error(
                "[django_athm:timeout]", extra={"url": url, "timeout": self.timeout}
            )
            raise

        except Exception as e:
            logger.error(
                "[django_athm:request_error]", extra={"url": url, "error": str(e)}
            )
            raise


def get_http_adapter():
    return SyncHTTPAdapter()
