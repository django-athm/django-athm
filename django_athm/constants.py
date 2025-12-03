from enum import Enum

API_BASE_URL = "https://www.athmovil.com"

REFUND_URL = "/api/v4/refundTransaction"
SEARCH_URL = "/api/v4/searchTransaction"
REPORT_URL = "/transactions/v4/transactionReport"

ERROR_DICT = {
    "3010": "publicToken is invalid",
    "3020": "publicToken is revoked",
    "3030": "publicToken is required",
    "3040": "privateToken is invalid",
    "3050": "privateToken is revoked",
    "3060": "privateToken is required",
    "3070": "tokens are from different accounts",
    "4010": "referenceNumber is required",
    "5010": "transaction does not exist",
    "5020": "transaction is from another business",
    "7010": "transaction already refunded",
    "7020": "amount is invalid",
    "7030": "amount is required",
    "7040": "error completing refund",
}

BUTTON_COLOR_DEFAULT = "btn"
BUTTON_COLOR_LIGHT = "btn-light"
BUTTON_COLOR_DARK = "btn-dark"

BUTTON_LANGUAGE_SPANISH = "es"
BUTTON_LANGUAGE_ENGLISH = "en"


class TransactionStatus(Enum):
    refunded = "REFUNDED"
    cancelled = "CANCELLED"
    expired = "EXPIRED"
    completed = "COMPLETED"


class TransactionType(Enum):
    ecommerce = "ECOMMERCE"
    refund = "REFUND"
    completed = "COMPLETED"
