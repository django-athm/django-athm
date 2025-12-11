from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from django_athm import utils


def test_safe_decimal_with_valid_values():
    assert utils.safe_decimal(100) == Decimal("100")
    assert utils.safe_decimal(100.50) == Decimal("100.50")
    assert utils.safe_decimal("100.50") == Decimal("100.50")
    assert utils.safe_decimal(Decimal("100.50")) == Decimal("100.50")


def test_safe_decimal_with_none():
    assert utils.safe_decimal(None) == Decimal("0")
    assert utils.safe_decimal(None, Decimal("99")) == Decimal("99")


def test_safe_decimal_with_invalid_values():
    assert utils.safe_decimal("invalid") == Decimal("0")
    assert utils.safe_decimal("invalid", Decimal("99")) == Decimal("99")


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


class TestNormalizePhoneNumber:
    def test_returns_digits_only(self):
        assert utils.normalize_phone_number("7875551234") == "7875551234"

    def test_strips_formatting_characters(self):
        assert utils.normalize_phone_number("(787) 555-1234") == "7875551234"
        assert utils.normalize_phone_number("787-555-1234") == "7875551234"
        assert utils.normalize_phone_number("787 555 1234") == "7875551234"
        assert utils.normalize_phone_number("+1-787-555-1234") == "17875551234"

    def test_handles_numeric_input(self):
        assert utils.normalize_phone_number(7875551234) == "7875551234"

    def test_returns_empty_string_for_none(self):
        assert utils.normalize_phone_number(None) == ""

    def test_returns_empty_string_for_empty_string(self):
        assert utils.normalize_phone_number("") == ""

    def test_returns_empty_string_for_whitespace_only(self):
        assert utils.normalize_phone_number("   ") == ""
