import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.orders import OrderCreate, OrderPage, OrderPublic, OrderQuotePublic
from app.services import orders as order_service

router = APIRouter()


@router.get("/quote", response_model=OrderQuotePublic)
def quote_order(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderQuotePublic:
    return order_service.quote_order(db, user)


@router.post("", response_model=OrderPublic, status_code=status.HTTP_201_CREATED)
def create_order(
    body: OrderCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderPublic:
    return order_service.create_order(db, user, body)


@router.get("", response_model=OrderPage)
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderPage:
    return order_service.list_orders(db, user, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderPublic)
def get_order(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderPublic:
    return order_service.get_order(db, user, order_id)
