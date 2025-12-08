from decimal import Decimal

from django_athm import utils


def test_safe_decimal_with_valid_values():
    """Test safe_decimal with various valid input types."""
    assert utils.safe_decimal(100) == Decimal("100")
    assert utils.safe_decimal(100.50) == Decimal("100.50")
    assert utils.safe_decimal("100.50") == Decimal("100.50")
    assert utils.safe_decimal(Decimal("100.50")) == Decimal("100.50")


def test_safe_decimal_with_none():
    """Test safe_decimal returns default when value is None."""
    assert utils.safe_decimal(None) is None
    assert utils.safe_decimal(None, Decimal("0")) == Decimal("0")


def test_safe_decimal_with_invalid_values():
    """Test safe_decimal returns default for invalid inputs."""
    assert utils.safe_decimal("invalid") is None
    assert utils.safe_decimal("invalid", Decimal("0")) == Decimal("0")
