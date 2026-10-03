import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.admin import (
    CouponPublic,
    CouponWrite,
    CustomerPage,
    DashboardPublic,
    OrderStatusUpdate,
    PaymentPage,
    ReviewAdminPage,
    StockUpdate,
    StoreSettingsPublic,
)
from app.schemas.catalog import ProductPublic
from app.schemas.orders import OrderPublic
from app.services import admin as admin_service

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/dashboard", response_model=DashboardPublic)
def dashboard(db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_admin)]) -> DashboardPublic:
    return admin_service.dashboard(db)


@router.get("/customers", response_model=CustomerPage)
def customers(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CustomerPage:
    return admin_service.list_customers(db, page=page, page_size=page_size)


@router.get("/payments", response_model=PaymentPage)
def payments(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaymentPage:
    return admin_service.list_payments(db, page=page, page_size=page_size)


@router.get("/reviews", response_model=ReviewAdminPage)
def reviews(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReviewAdminPage:
    return admin_service.list_reviews(db, page=page, page_size=page_size)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    admin_service.delete_review(db, review_id)


@router.get("/coupons", response_model=list[CouponPublic])
def coupons(db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_admin)]) -> list[CouponPublic]:
    return admin_service.list_coupons(db)


@router.post("/coupons", response_model=CouponPublic, status_code=status.HTTP_201_CREATED)
def create_coupon(
    body: CouponWrite,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> CouponPublic:
    return admin_service.create_coupon(db, body)


@router.put("/coupons/{coupon_id}", response_model=CouponPublic)
def update_coupon(
    coupon_id: uuid.UUID,
    body: CouponWrite,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> CouponPublic:
    return admin_service.update_coupon(db, coupon_id, body)


@router.delete("/coupons/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coupon(
    coupon_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    admin_service.delete_coupon(db, coupon_id)


@router.patch("/orders/{order_id}", response_model=OrderPublic)
def update_order(
    order_id: uuid.UUID,
    body: OrderStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> OrderPublic:
    return admin_service.set_order_status(db, order_id, body.status)


@router.patch("/products/{product_id}/stock", response_model=ProductPublic)
def update_product_stock(
    product_id: uuid.UUID,
    body: StockUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> ProductPublic:
    return admin_service.set_stock(db, product_id, body.stock_quantity)


@router.get("/settings", response_model=StoreSettingsPublic)
def store_settings(_: Annotated[User, Depends(require_admin)]) -> StoreSettingsPublic:
    return admin_service.store_settings()
