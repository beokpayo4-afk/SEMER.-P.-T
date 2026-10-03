import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.engagement import ReviewCreate, ReviewPage, WishlistAdd, WishlistResponse
from app.services import engagement as engagement_service

review_router = APIRouter()
wishlist_router = APIRouter()


@review_router.get("/{product_id}/reviews", response_model=ReviewPage)
def list_reviews(product_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> ReviewPage:
    return engagement_service.list_reviews(db, product_id)


@review_router.post("/{product_id}/reviews", response_model=ReviewPage, status_code=status.HTTP_201_CREATED)
def create_review(
    product_id: uuid.UUID,
    body: ReviewCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ReviewPage:
    return engagement_service.create_review(db, product_id, user, body)


@wishlist_router.get("", response_model=WishlistResponse)
def list_wishlist(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WishlistResponse:
    return engagement_service.list_wishlist(db, user)


@wishlist_router.post("", response_model=WishlistResponse, status_code=status.HTTP_201_CREATED)
def add_wishlist_item(
    body: WishlistAdd,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WishlistResponse:
    return engagement_service.add_wishlist_item(db, user, body.product_id)


@wishlist_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_wishlist_item(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    engagement_service.remove_wishlist_item(db, user, product_id)
