import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.payments import PaymentCreate, PaymentPublic, PaymentVerify
from app.services.payments import service as payment_service

router = APIRouter()


@router.post("/create", response_model=PaymentPublic)
def create_payment(
    body: PaymentCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PaymentPublic:
    payment_service.screen_request(body.model_dump())
    return payment_service.create_payment(db, user, body.order_id, body.payment_method)


@router.post("/verify", response_model=PaymentPublic)
def verify_payment(
    body: PaymentVerify,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PaymentPublic:
    payment_service.screen_request(body.model_dump())
    return payment_service.verify_payment(db, user, body.payment_id, body.transaction_id)


@router.post("/webhook", response_model=PaymentPublic)
async def payment_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> PaymentPublic:
    body = await request.body()
    return payment_service.handle_webhook(db, body, request.headers.get("X-Payment-Signature"))
