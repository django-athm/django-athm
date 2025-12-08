from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

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


class TestValidateTotal:
    def test_valid_total(self):
        assert utils.validate_total("100.00") == Decimal("100.00")
        assert utils.validate_total(50) == Decimal("50")
        assert utils.validate_total(Decimal("1.00")) == Decimal("1.00")
        assert utils.validate_total(1500) == Decimal("1500")

    def test_invalid_total_raises_error(self):
        with pytest.raises(ValidationError, match="Invalid total"):
            utils.validate_total("invalid")
        with pytest.raises(ValidationError, match="Invalid total"):
            utils.validate_total(None)

    def test_total_below_minimum_raises_error(self):
        with pytest.raises(ValidationError, match=r"between 1.00 and 1500.00"):
            utils.validate_total("0.99")

    def test_total_above_maximum_raises_error(self):
        with pytest.raises(ValidationError, match=r"between 1.00 and 1500.00"):
            utils.validate_total("1500.01")


class TestValidatePhoneNumber:
    def test_valid_phone_number(self):
        assert utils.validate_phone_number("7875551234") == "7875551234"

    def test_strips_dashes_and_spaces(self):
        assert utils.validate_phone_number("787-555-1234") == "7875551234"
        assert utils.validate_phone_number("787 555 1234") == "7875551234"
        assert utils.validate_phone_number(" 787-555-1234 ") == "7875551234"

    def test_invalid_phone_raises_error(self):
        with pytest.raises(ValidationError, match="Invalid phone number"):
            utils.validate_phone_number("")
        with pytest.raises(ValidationError, match="Invalid phone number"):
            utils.validate_phone_number(None)
        with pytest.raises(ValidationError, match="Invalid phone number"):
            utils.validate_phone_number("123")  # too short
        with pytest.raises(ValidationError, match="Invalid phone number"):
            utils.validate_phone_number("12345678901")  # too long
        with pytest.raises(ValidationError, match="Invalid phone number"):
            utils.validate_phone_number("787555abcd")  # non-digit
