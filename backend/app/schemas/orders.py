import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

OrderStatusPublic = Literal[
    "PENDING",
    "CONFIRMED",
    "PROCESSING",
    "SHIPPED",
    "DELIVERED",
    "CANCELLED",
    "REFUNDED",
]
PaymentStatusPublic = Literal["PENDING", "PAID", "FAILED", "REFUNDED"]


def _required_text(value: str, message: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError(message)
    return cleaned


class AddressInput(BaseModel):
    address: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=1, max_length=80)
    postal_code: str = Field(min_length=1, max_length=12)
    country: str = Field(min_length=2, max_length=2)

    @field_validator("address", "city", "state")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return _required_text(value, "This field is required")

    @field_validator("postal_code")
    @classmethod
    def clean_postal_code(cls, value: str) -> str:
        cleaned = "".join(value.split()).upper()
        if not cleaned:
            raise ValueError("Postal code is required")
        return cleaned

    @field_validator("country")
    @classmethod
    def clean_country(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 2 or not cleaned.isalpha():
            raise ValueError("Use a 2-letter country code")
        return cleaned


class CustomerInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=20)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _required_text(value, "Name is required")

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str) -> str:
        cleaned = "".join(character for character in value if character.isdigit() or character == "+")
        digits = cleaned[1:] if cleaned.startswith("+") else cleaned
        if not digits.isdigit() or not 8 <= len(digits) <= 15:
            raise ValueError("Enter a valid phone number")
        return cleaned


class OrderCreate(BaseModel):
    customer: CustomerInput
    billing: AddressInput
    shipping_same_as_billing: bool = True
    shipping: AddressInput | None = None
    payment_method: Literal["cod", "upi"] = "cod"

    @model_validator(mode="after")
    def shipping_required(self) -> "OrderCreate":
        if not self.shipping_same_as_billing and self.shipping is None:
            raise ValueError("Shipping address is required")
        return self


class AddressPublic(BaseModel):
    address: str
    city: str
    state: str
    postal_code: str
    country: str


class OrderLinePublic(BaseModel):
    name: str
    variant_name: str | None
    sku: str
    quantity: int
    list_price: int
    unit_price: int
    line_subtotal: int
    line_discount: int
    line_total: int


class OrderQuotePublic(BaseModel):
    items: list[OrderLinePublic]
    subtotal: int
    discount: int
    shipping: int
    tax: int
    total: int
    payment_method: str


class OrderPublic(OrderQuotePublic):
    id: uuid.UUID
    order_number: str
    status: OrderStatusPublic
    payment_status: PaymentStatusPublic
    customer_name: str
    customer_email: EmailStr
    customer_phone: str
    billing_address: AddressPublic
    shipping_address: AddressPublic
    created_at: datetime


class OrderPage(BaseModel):
    items: list[OrderPublic]
    page: int
    page_size: int
    total: int
