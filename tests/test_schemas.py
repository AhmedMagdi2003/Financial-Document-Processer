from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import Item


def test_invoice_measured_quantities_allow_more_than_money_precision():
    item = Item(description="Cloud compute units", quantity="655.931967", unit_price="0.0076")

    assert item.quantity == Decimal("655.931967")
    assert item.unit_price == Decimal("0.0076")


def test_quantity_precision_is_bounded_without_four_digit_money_limit():
    with pytest.raises(ValidationError, match="Maximum twelve fractional digits"):
        Item(description="Measured usage", quantity="0.1234567890123")

    with pytest.raises(ValidationError, match="Maximum four fractional digits"):
        Item(description="Measured usage", quantity="1", unit_price="0.123456")
