API_BASE_URL = "https://www.athmovil.com"

REFUND_URL = "/rs/v2/refund"
STATUS_URL = "/rs/v2/transactionStatus"
LIST_URL = "/transactions/v1/business"

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

REFUNDED_STATUS = "refunded"
CANCELLED_STATUS = "cancelled"
EXPIRED_STATUS = "expired"
COMPLETED_STATUS = "completed"
