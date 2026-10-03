import uuid
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.exceptions import APIError
from app.models.catalog import Category, Product, Review
from app.models.commerce import Coupon, Order, Payment
from app.models.enquiries import EventEnquiry, TravelEnquiry
from app.models.enums import DiscountType, OrderStatus, RecordStatus, UserRole
from app.models.identity import User
from app.schemas.admin import (
    CouponPublic,
    CouponWrite,
    CustomerPage,
    CustomerPublic,
    DashboardCategory,
    DashboardMonth,
    DashboardPublic,
    PaymentAdmin,
    PaymentPage,
    ReviewAdmin,
    ReviewAdminPage,
    StoreSettingsPublic,
)
from app.schemas.orders import OrderPublic, OrderStatusPublic
from app.services.catalog import update_stock
from app.services.orders import update_order_status

LOW_STOCK_THRESHOLD = 5


def dashboard(db: Session) -> DashboardPublic:
    sales_filter = Order.status.notin_([OrderStatus.cancelled, OrderStatus.refunded])
    total_sales = db.scalar(select(func.coalesce(func.sum(Order.total_paise), 0)).where(sales_filter)) or 0
    return DashboardPublic(
        total_orders=db.scalar(select(func.count()).select_from(Order)) or 0,
        total_sales=int(total_sales),
        pending_orders=_count_orders(db, OrderStatus.pending),
        completed_orders=_count_orders(db, OrderStatus.delivered),
        total_customers=db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.customer)
        )
        or 0,
        total_products=db.scalar(select(func.count()).select_from(Product)) or 0,
        low_stock_products=db.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.status == RecordStatus.active, Product.stock_quantity <= LOW_STOCK_THRESHOLD)
        )
        or 0,
        travel_enquiries=db.scalar(select(func.count()).select_from(TravelEnquiry)) or 0,
        event_enquiries=db.scalar(select(func.count()).select_from(EventEnquiry)) or 0,
        months=_months(db),
        categories=_categories(db),
    )


def list_customers(db: Session, *, page: int, page_size: int) -> CustomerPage:
    filters = [User.role == UserRole.customer]
    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    users = db.scalars(
        select(User)
        .where(*filters)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return CustomerPage(
        items=[
            CustomerPublic(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                created_at=user.created_at,
            )
            for user in users
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


def list_payments(db: Session, *, page: int, page_size: int) -> PaymentPage:
    total = db.scalar(select(func.count()).select_from(Payment)) or 0
    payments = db.scalars(
        select(Payment).order_by(Payment.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return PaymentPage(
        items=[
            PaymentAdmin(
                id=payment.id,
                order_id=payment.order_id,
                amount=payment.amount_paise,
                currency=payment.currency,
                provider=payment.provider,
                transaction_id=payment.transaction_id,
                status=payment.status.value.upper(),  # type: ignore[arg-type]
                payment_method=payment.payment_method,
                created_at=payment.created_at,
            )
            for payment in payments
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


def list_reviews(db: Session, *, page: int, page_size: int) -> ReviewAdminPage:
    total = db.scalar(select(func.count()).select_from(Review)) or 0
    reviews = db.scalars(
        select(Review)
        .options(selectinload(Review.user), selectinload(Review.product))
        .order_by(Review.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ReviewAdminPage(
        items=[
            ReviewAdmin(
                id=review.id,
                product_id=review.product_id,
                product_name=review.product.name,
                rating=review.rating,
                comment=review.comment,
                author_name=review.user.full_name,
                created_at=review.created_at,
            )
            for review in reviews
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


def delete_review(db: Session, review_id: uuid.UUID) -> None:
    review = db.get(Review, review_id)
    if review is None:
        raise APIError(status_code=404, detail="Review not found")
    db.delete(review)
    db.commit()


def list_coupons(db: Session) -> list[CouponPublic]:
    coupons = db.scalars(select(Coupon).order_by(Coupon.created_at.desc())).all()
    return [_coupon_public(coupon) for coupon in coupons]


def create_coupon(db: Session, data: CouponWrite) -> CouponPublic:
    _check_discount(data)
    coupon = Coupon(
        code=data.code,
        discount_type=data.discount_type,
        discount_value=data.discount_value,
        is_active=data.is_active,
        expires_at=data.expires_at,
    )
    db.add(coupon)
    _commit(db, "Code is already in use")
    db.refresh(coupon)
    return _coupon_public(coupon)


def update_coupon(db: Session, coupon_id: uuid.UUID, data: CouponWrite) -> CouponPublic:
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise APIError(status_code=404, detail="Coupon not found")
    _check_discount(data)
    coupon.code = data.code
    coupon.discount_type = data.discount_type
    coupon.discount_value = data.discount_value
    coupon.is_active = data.is_active
    coupon.expires_at = data.expires_at
    _commit(db, "Code is already in use")
    db.refresh(coupon)
    return _coupon_public(coupon)


def delete_coupon(db: Session, coupon_id: uuid.UUID) -> None:
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise APIError(status_code=404, detail="Coupon not found")
    db.delete(coupon)
    db.commit()


def set_order_status(db: Session, order_id: uuid.UUID, status: OrderStatusPublic) -> OrderPublic:
    return update_order_status(db, order_id, OrderStatus(status.lower()))


def set_stock(db: Session, product_id: uuid.UUID, stock_quantity: int):
    return update_stock(db, product_id, stock_quantity)


def store_settings() -> StoreSettingsPublic:
    return StoreSettingsPublic(
        store_name=settings.app_name,
        currency=settings.payment_currency,
        payment_provider=settings.payment_provider,
        low_stock_threshold=LOW_STOCK_THRESHOLD,
        environment=settings.environment,
    )


def _count_orders(db: Session, status: OrderStatus) -> int:
    return db.scalar(select(func.count()).select_from(Order).where(Order.status == status)) or 0


def _months(db: Session) -> list[DashboardMonth]:
    starts = _month_starts(6)
    first = starts[0]
    sales_case = case(
        (Order.status.notin_([OrderStatus.cancelled, OrderStatus.refunded]), Order.total_paise),
        else_=0,
    )
    bucket = func.to_char(Order.created_at, "YYYY-MM")
    rows = db.execute(
        select(
            bucket.label("month"),
            func.count().label("orders"),
            func.coalesce(func.sum(sales_case), 0).label("sales"),
        )
        .where(Order.created_at >= first)
        .group_by(bucket)
    ).all()
    by_month = {row.month: (int(row.sales), int(row.orders)) for row in rows}
    return [
        DashboardMonth(
            month=start.strftime("%Y-%m"),
            sales=by_month.get(start.strftime("%Y-%m"), (0, 0))[0],
            orders=by_month.get(start.strftime("%Y-%m"), (0, 0))[1],
        )
        for start in starts
    ]


def _categories(db: Session) -> list[DashboardCategory]:
    rows = db.execute(
        select(Category.name, func.count(Product.id))
        .join(Product, Product.category_id == Category.id)
        .where(Product.status != RecordStatus.archived)
        .group_by(Category.name)
        .order_by(func.count(Product.id).desc(), Category.name.asc())
    ).all()
    return [DashboardCategory(name=name, products=int(count)) for name, count in rows]


def _month_starts(count: int) -> list[date]:
    today = date.today()
    year, month = today.year, today.month
    starts: list[date] = []
    for _ in range(count):
        starts.append(date(year, month, 1))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(starts))


def _check_discount(data: CouponWrite) -> None:
    if data.discount_type == DiscountType.percent and not 1 <= data.discount_value <= 100:
        raise APIError(status_code=422, detail="Percent discount must be between 1 and 100")


def _coupon_public(coupon: Coupon) -> CouponPublic:
    return CouponPublic(
        id=coupon.id,
        code=coupon.code,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        is_active=coupon.is_active,
        expires_at=coupon.expires_at,
    )


def _commit(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(status_code=409, detail=detail)
