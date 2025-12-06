"""
ATH Móvil API client wrapper.

Provides a Django-friendly interface to the python-athm library with
proper configuration management and error handling.
"""
import logging
from decimal import Decimal
from typing import Any, Optional

from athm import ATHMovilClient as BaseATHMovilClient
from athm.exceptions import ATHMovilError, ValidationError

from .conf import settings

logger = logging.getLogger(__name__)


class ATHMClient:
    """
    Wrapper around python-athm's ATHMovilClient.

    Automatically uses tokens from Django settings and provides
    convenience methods for common operations.
    """

    def __init__(
        self,
        public_token: Optional[str] = None,
        private_token: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize the ATH Móvil client.

        Args:
            public_token: Public API token (defaults to settings.PUBLIC_TOKEN)
            private_token: Private API token (defaults to settings.PRIVATE_TOKEN)
            timeout: Request timeout in seconds
        """
        self.public_token = public_token or settings.PUBLIC_TOKEN
        self.private_token = private_token or settings.PRIVATE_TOKEN
        self.timeout = timeout

        if not self.public_token:
            raise ValueError(
                "DJANGO_ATHM_PUBLIC_TOKEN must be set in Django settings"
            )

    def _get_client(self, require_private: bool = False) -> BaseATHMovilClient:
        """
        Get configured ATHMovilClient instance.

        Args:
            require_private: Whether private token is required

        Returns:
            Configured ATHMovilClient

        Raises:
            ValueError: If required tokens are missing
        """
        if require_private and not self.private_token:
            raise ValueError(
                "DJANGO_ATHM_PRIVATE_TOKEN is required for this operation"
            )

        return BaseATHMovilClient(
            public_token=self.public_token,
            private_token=self.private_token if require_private else None,
            timeout=self.timeout,
        )

    def create_payment(
        self,
        total: Decimal,
        phone_number: Optional[str] = None,
        metadata1: Optional[str] = None,
        metadata2: Optional[str] = None,
        items: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Create a new payment.

        Args:
            total: Total payment amount
            phone_number: Customer phone number (optional)
            metadata1: Custom metadata field 1
            metadata2: Custom metadata field 2
            items: List of item dictionaries

        Returns:
            dict containing ecommerce_id and auth_token

        Raises:
            ATHMovilError: If payment creation fails
            ValidationError: If parameters are invalid
        """
        client = self._get_client()

        # Convert Decimal to float for API
        total_float = float(total)

        logger.info(
            "[django_athm:create_payment]",
            extra={
                "total": total_float,
                "phone_number": phone_number,
                "has_items": bool(items),
            },
        )

        try:
            response = client.create_payment(
                total=total_float,
                phone_number=phone_number,
                metadata1=metadata1,
                metadata2=metadata2,
                items=items,
            )
            logger.debug(
                "[django_athm:create_payment:success]",
                extra={"ecommerce_id": response.get("ecommerce_id")},
            )
            return response
        except (ATHMovilError, ValidationError) as e:
            logger.error(
                "[django_athm:create_payment:error]",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise

    def check_payment_status(self, ecommerce_id: str) -> dict[str, Any]:
        """
        Check the status of a payment.

        Args:
            ecommerce_id: The ecommerce transaction ID

        Returns:
            dict containing payment status and details

        Raises:
            ATHMovilError: If status check fails
        """
        client = self._get_client()

        logger.debug(
            "[django_athm:check_status]", extra={"ecommerce_id": ecommerce_id}
        )

        try:
            return client.check_payment_status(ecommerce_id)
        except ATHMovilError as e:
            logger.error(
                "[django_athm:check_status:error]",
                extra={"ecommerce_id": ecommerce_id, "error": str(e)},
                exc_info=True,
            )
            raise

    def authorize_payment(self, auth_token: str) -> dict[str, Any]:
        """
        Authorize a confirmed payment.

        Args:
            auth_token: Authorization token from create_payment

        Returns:
            dict containing transaction details

        Raises:
            ATHMovilError: If authorization fails
        """
        client = self._get_client()

        logger.debug("[django_athm:authorize_payment]")

        try:
            response = client.authorize_payment(auth_token)
            logger.info(
                "[django_athm:authorize_payment:success]",
                extra={"reference_number": response.get("referenceNumber")},
            )
            return response
        except ATHMovilError as e:
            logger.error(
                "[django_athm:authorize_payment:error]",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise

    def cancel_payment(self, ecommerce_id: str) -> dict[str, Any]:
        """
        Cancel a pending payment.

        Args:
            ecommerce_id: The ecommerce transaction ID

        Returns:
            dict containing cancellation confirmation

        Raises:
            ATHMovilError: If cancellation fails
        """
        client = self._get_client()

        logger.info(
            "[django_athm:cancel_payment]", extra={"ecommerce_id": ecommerce_id}
        )

        try:
            response = client.cancel_payment(ecommerce_id)
            logger.debug("[django_athm:cancel_payment:success]")
            return response
        except ATHMovilError as e:
            logger.error(
                "[django_athm:cancel_payment:error]",
                extra={"ecommerce_id": ecommerce_id, "error": str(e)},
                exc_info=True,
            )
            raise

    def refund_payment(
        self, reference_number: str, amount: Optional[Decimal] = None
    ) -> dict[str, Any]:
        """
        Refund a completed payment.

        Args:
            reference_number: Transaction reference number
            amount: Amount to refund (None for full refund)

        Returns:
            dict containing refund confirmation

        Raises:
            ATHMovilError: If refund fails
        """
        client = self._get_client(require_private=True)

        # Convert Decimal to float for API
        amount_float = float(amount) if amount is not None else None

        logger.info(
            "[django_athm:refund_payment]",
            extra={"reference_number": reference_number, "amount": amount_float},
        )

        try:
            response = client.refund_payment(reference_number, amount_float)
            logger.info(
                "[django_athm:refund_payment:success]",
                extra={
                    "reference_number": reference_number,
                    "refunded_amount": response.get("refundedAmount"),
                },
            )
            return response
        except ATHMovilError as e:
            logger.error(
                "[django_athm:refund_payment:error]",
                extra={"reference_number": reference_number, "error": str(e)},
                exc_info=True,
            )
            raise

    def subscribe_webhook(
        self,
        webhook_url: str,
        ecommerce_payment: bool = True,
        ecommerce_refund: bool = True,
        ecommerce_cancel: bool = True,
        ecommerce_expire: bool = True,
    ) -> dict[str, Any]:
        """
        Subscribe to webhook events.

        Args:
            webhook_url: URL to receive webhooks
            ecommerce_payment: Subscribe to payment completed events
            ecommerce_refund: Subscribe to refund sent events
            ecommerce_cancel: Subscribe to payment cancelled events
            ecommerce_expire: Subscribe to payment expired events

        Returns:
            dict containing subscription confirmation

        Raises:
            ATHMovilError: If subscription fails
        """
        client = self._get_client(require_private=True)

        logger.info(
            "[django_athm:subscribe_webhook]",
            extra={
                "webhook_url": webhook_url,
                "events": {
                    "payment": ecommerce_payment,
                    "refund": ecommerce_refund,
                    "cancel": ecommerce_cancel,
                    "expire": ecommerce_expire,
                },
            },
        )

        try:
            response = client.subscribe_webhook(
                webhook_url=webhook_url,
                ecommerce_payment=ecommerce_payment,
                ecommerce_refund=ecommerce_refund,
                ecommerce_cancel=ecommerce_cancel,
                ecommerce_expire=ecommerce_expire,
            )
            logger.info("[django_athm:subscribe_webhook:success]")
            return response
        except ATHMovilError as e:
            logger.error(
                "[django_athm:subscribe_webhook:error]",
                extra={"webhook_url": webhook_url, "error": str(e)},
                exc_info=True,
            )
            raise

    def parse_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Parse and validate a webhook payload.

        Args:
            payload: Raw webhook payload dict

        Returns:
            Parsed webhook data

        Raises:
            ValidationError: If payload is invalid
        """
        client = self._get_client()

        logger.debug("[django_athm:parse_webhook]")

        try:
            return client.parse_webhook(payload)
        except ValidationError as e:
            logger.error(
                "[django_athm:parse_webhook:error]",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise
