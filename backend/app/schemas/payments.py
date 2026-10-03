import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PaymentStatusPublic = Literal["PENDING", "PAID", "FAILED", "REFUNDED"]


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: uuid.UUID
    payment_method: str = Field(min_length=1, max_length=32)


class PaymentVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_id: uuid.UUID
    transaction_id: str | None = Field(default=None, max_length=120)


class PaymentPublic(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    amount: int
    currency: str
    provider: str
    transaction_id: str | None
    status: PaymentStatusPublic
    payment_method: str
    created_at: datetime
    updated_at: datetime
