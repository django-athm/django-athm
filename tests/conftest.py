import json
from pathlib import Path

import pytest


@pytest.fixture
def payment_completed_webhook_payload():
    """Real payment completed webhook payload (anonymized)."""
    fixture_path = Path(__file__).parent / "fixtures" / "payment_completed_webhook.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def refund_webhook_payload():
    """Real refund webhook payload (anonymized)."""
    fixture_path = Path(__file__).parent / "fixtures" / "refund_webhook.json"
    with open(fixture_path) as f:
        return json.load(f)
