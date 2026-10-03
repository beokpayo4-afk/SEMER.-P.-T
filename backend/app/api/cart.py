import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartPublic
from app.services import cart as cart_service

router = APIRouter()


@router.get("", response_model=CartPublic)
def get_cart(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> CartPublic:
    return cart_service.get_cart(db, user)


@router.post("/items", response_model=CartPublic, status_code=status.HTTP_201_CREATED)
def add_item(
    body: CartItemCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> CartPublic:
    return cart_service.add_item(db, user, body)


@router.put("/items/{item_id}", response_model=CartPublic)
def update_item(
    item_id: uuid.UUID,
    body: CartItemUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> CartPublic:
    return cart_service.update_item(db, user, item_id, body.quantity)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    item_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    cart_service.remove_item(db, user, item_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    cart_service.clear_cart(db, user)
