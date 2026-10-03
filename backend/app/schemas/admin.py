import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import DiscountType
from app.schemas.orders import OrderStatusPublic
from app.schemas.payments import PaymentStatusPublic


class DashboardMonth(BaseModel):
    month: str
    sales: int
    orders: int


class DashboardCategory(BaseModel):
    name: str
    products: int


class DashboardPublic(BaseModel):
    total_orders: int
    total_sales: int
    pending_orders: int
    completed_orders: int
    total_customers: int
    total_products: int
    low_stock_products: int
    travel_enquiries: int
    event_enquiries: int
    months: list[DashboardMonth]
    categories: list[DashboardCategory]


class CustomerPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime


class CustomerPage(BaseModel):
    items: list[CustomerPublic]
    page: int
    page_size: int
    total: int


class PaymentAdmin(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    amount: int
    currency: str
    provider: str
    transaction_id: str | None
    status: PaymentStatusPublic
    payment_method: str
    created_at: datetime


class PaymentPage(BaseModel):
    items: list[PaymentAdmin]
    page: int
    page_size: int
    total: int


class ReviewAdmin(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    rating: int
    comment: str | None
    author_name: str
    created_at: datetime


class ReviewAdminPage(BaseModel):
    items: list[ReviewAdmin]
    page: int
    page_size: int
    total: int


class CouponWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=3, max_length=40)
    discount_type: DiscountType
    discount_value: int = Field(ge=1)
    is_active: bool = True
    expires_at: datetime | None = None

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        code = "".join(value.split()).upper()
        if not code.isalnum():
            raise ValueError("Code must use letters and numbers")
        return code

    @field_validator("discount_value")
    @classmethod
    def value_positive(cls, value: int) -> int:
        return value


class CouponPublic(BaseModel):
    id: uuid.UUID
    code: str
    discount_type: DiscountType
    discount_value: int
    is_active: bool
    expires_at: datetime | None


class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatusPublic


class StockUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_quantity: int = Field(ge=0)


class StoreSettingsPublic(BaseModel):
    store_name: str
    currency: str
    payment_provider: str
    low_stock_threshold: int
    environment: str
