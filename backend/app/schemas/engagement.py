import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewPublic(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    rating: int
    comment: str | None
    author_name: str
    created_at: datetime


class ReviewPage(BaseModel):
    items: list[ReviewPublic]
    total: int
    rating_average: float | None
    review_count: int


class WishlistResponse(BaseModel):
    product_ids: list[uuid.UUID]


class WishlistAdd(BaseModel):
    product_id: uuid.UUID
