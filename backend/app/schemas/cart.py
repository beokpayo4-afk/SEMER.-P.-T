import uuid

from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    quantity: int = Field(ge=1, le=100)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=100)


class CartItemPublic(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None
    name: str
    variant_name: str | None
    sku: str
    image_url: str | None
    quantity: int
    stock_quantity: int
    list_price: int
    unit_price: int
    line_subtotal: int
    line_discount: int
    line_total: int


class CartPublic(BaseModel):
    id: uuid.UUID
    items: list[CartItemPublic]
    subtotal: int
    discount: int
    total: int
