from datetime import date as Date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

import pycountry
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def exact_money(value):
    if isinstance(value, float):
        raise ValueError("Money must be a decimal string, never a float")
    if value is not None:
        try:
            number = Decimal(value)
        except (InvalidOperation, TypeError) as exc:
            raise ValueError("Invalid decimal money") from exc
        if not number.is_finite() or abs(number) >= Decimal("1000000000000000"):
            raise ValueError("Invalid or out-of-range money")
        if number.as_tuple().exponent < -4:
            raise ValueError("Maximum four fractional digits")
    return value


Money = Annotated[Decimal, BeforeValidator(exact_money)]


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(max_length=1000)
    quantity: Money | None = None
    unit_price: Money | None = None
    line_amount: Money | None = None


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_type: Literal["invoice", "receipt", "credit_note", "unknown"] = "unknown"
    vendor: str | None = Field(default=None, max_length=250)
    date: Date | None = None
    document_number: str | None = Field(default=None, max_length=150)
    description: str = Field(default="", max_length=4000)
    subtotal: Money | None = None
    discount: Money | None = None
    tax: Money | None = None
    grand_total: Money | None = None
    amount_due: Money | None = None
    amount_paid: Money | None = None
    currency: str | None = None
    tax_mode: Literal["inclusive", "exclusive", "unknown"] = "unknown"
    discount_explicit: bool = False
    items: list[Item] = Field(default_factory=list, max_length=100)
    evidence: list[str] = Field(default_factory=list, max_length=20)
    category_id: str | None = Field(default=None, max_length=80)
    category_rationale: str = Field(default="", max_length=1000)

    @field_validator("currency")
    @classmethod
    def iso_currency(cls, value):
        if value is None or value == "":
            return None
        if not pycountry.currencies.get(alpha_3=value):
            raise ValueError("Use an uppercase ISO 4217 currency code or null")
        return value


class CategoryChoice(BaseModel):
    category_id: str = Field(max_length=80)
    rationale: str = Field(max_length=1000)


class ReviewInput(BaseModel):
    version: int = Field(ge=1)
    candidate: Candidate


class ConfirmInput(BaseModel):
    version: int = Field(ge=1)
    justification: str = Field(default="", max_length=2000)


class CategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    definition: str = Field(min_length=10, max_length=2000)
    active: bool
