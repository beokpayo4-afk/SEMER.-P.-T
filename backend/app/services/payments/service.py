import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import APIError
from app.models.commerce import Order, Payment
from app.models.enums import OrderStatus, PaymentStatus, UserRole
from app.models.identity import User
from app.schemas.payments import PaymentPublic
from app.services.payments.provider import ALLOWED_METHODS, get_payment_provider, reject_sensitive

_TRANSITIONS = {
    PaymentStatus.pending: {PaymentStatus.paid, PaymentStatus.failed},
    PaymentStatus.paid: {PaymentStatus.refunded},
    PaymentStatus.failed: set(),
    PaymentStatus.refunded: set(),
}


def attach_payment(db: Session, order: Order, payment_method: str) -> Payment:
    method = _method(payment_method)
    provider = get_payment_provider()
    transaction_id, status = provider.start(
        amount_paise=order.total_paise,
        currency=settings.payment_currency,
        payment_method=method,
    )
    payment = Payment(
        order_id=order.id,
        amount_paise=order.total_paise,
        currency=settings.payment_currency,
        provider=provider.name,
        transaction_id=transaction_id,
        status=status,
        payment_method=method,
    )
    db.add(payment)
    return payment


def create_payment(db: Session, user: User, order_id: uuid.UUID, payment_method: str) -> PaymentPublic:
    order = _owned_order(db, user, order_id)
    if order.status in {OrderStatus.cancelled, OrderStatus.refunded}:
        raise APIError(status_code=409, detail="This order cannot be paid")
    method = _method(payment_method)
    existing = _latest(db, order.id)
    if existing is not None and existing.status == PaymentStatus.paid:
        raise APIError(status_code=409, detail="This order is already paid")
    if existing is not None and existing.status == PaymentStatus.pending:
        if existing.payment_method == method:
            return present(existing)
        raise APIError(status_code=409, detail="A payment already exists for this order")
    try:
        payment = attach_payment(db, order, method)
        db.commit()
    except APIError:
        db.rollback()
        raise
    db.refresh(payment)
    return present(payment)


def verify_payment(
    db: Session,
    user: User,
    payment_id: uuid.UUID,
    transaction_id: str | None,
) -> PaymentPublic:
    payment = _owned_payment(db, user, payment_id)
    if transaction_id is not None and transaction_id != payment.transaction_id:
        raise APIError(status_code=422, detail="Payment could not be verified")
    _amounts_match(payment)
    provider = get_payment_provider()
    if provider.name != payment.provider:
        raise APIError(status_code=409, detail="Payment could not be verified")
    status = provider.verify(
        transaction_id=payment.transaction_id,
        amount_paise=payment.amount_paise,
        currency=payment.currency,
        current_status=payment.status,
    )
    try:
        _apply(payment, status)
        db.commit()
    except APIError:
        db.rollback()
        raise
    db.refresh(payment)
    return present(payment)


def handle_webhook(db: Session, body: bytes, signature: str | None) -> PaymentPublic:
    event = get_payment_provider().parse_webhook(body, signature)
    payment = db.scalar(select(Payment).where(Payment.transaction_id == event.transaction_id))
    if payment is None or payment.order is None:
        raise APIError(status_code=404, detail="Payment not found")
    try:
        _amounts_match(payment)
        _apply(payment, event.status)
        db.commit()
    except APIError:
        db.rollback()
        raise
    db.refresh(payment)
    return present(payment)


def present(payment: Payment) -> PaymentPublic:
    return PaymentPublic(
        id=payment.id,
        order_id=payment.order_id,
        amount=payment.amount_paise,
        currency=payment.currency,
        provider=payment.provider,
        transaction_id=payment.transaction_id,
        status=payment.status.value.upper(),  # type: ignore[arg-type]
        payment_method=payment.payment_method,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


def _apply(payment: Payment, status: PaymentStatus) -> None:
    if status == payment.status:
        return
    if status not in _TRANSITIONS[payment.status]:
        raise APIError(status_code=409, detail="Payment status cannot be changed")
    order = payment.order
    if status == PaymentStatus.paid and order.status == OrderStatus.cancelled:
        raise APIError(status_code=409, detail="Payment could not be applied")
    payment.status = status
    if status == PaymentStatus.paid and order.status == OrderStatus.pending:
        order.status = OrderStatus.confirmed
    elif status == PaymentStatus.refunded:
        order.status = OrderStatus.refunded


def _amounts_match(payment: Payment) -> None:
    if payment.amount_paise != payment.order.total_paise or payment.currency != settings.payment_currency:
        raise APIError(status_code=409, detail="Payment amount does not match the order")


def _method(payment_method: str) -> str:
    method = payment_method.strip().lower()
    if method not in ALLOWED_METHODS:
        raise APIError(status_code=422, detail="Unsupported payment method")
    return method


def _owned_order(db: Session, user: User, order_id: uuid.UUID) -> Order:
    order = db.get(Order, order_id)
    if order is None or (user.role != UserRole.admin and order.user_id != user.id):
        raise APIError(status_code=404, detail="Order not found")
    return order


def _owned_payment(db: Session, user: User, payment_id: uuid.UUID) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise APIError(status_code=404, detail="Payment not found")
    _owned_order(db, user, payment.order_id)
    return payment


def _latest(db: Session, order_id: uuid.UUID) -> Payment | None:
    return db.scalar(
        select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at.desc()).limit(1)
    )


def screen_request(payload: object) -> None:
    reject_sensitive(payload)
