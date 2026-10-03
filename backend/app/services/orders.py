import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import APIError
from app.models.catalog import Product, ProductVariant
from app.models.commerce import Cart, CartItem, Order, OrderItem
from app.models.enums import CartStatus, OrderStatus, RecordStatus, UserRole
from app.models.identity import Address, User
from app.schemas.orders import (
    AddressInput,
    AddressPublic,
    CustomerInput,
    OrderCreate,
    OrderLinePublic,
    OrderPage,
    OrderPublic,
    OrderQuotePublic,
)
from app.services.payments.service import attach_payment
from app.services.pricing import fulfillment_charges, quote_line, quote_totals

PAYMENT_METHOD = "cod"


def quote_order(db: Session, user: User) -> OrderQuotePublic:
    cart = _active_cart(db, user)
    if cart is None or not cart.items:
        shipping, tax, total = fulfillment_charges(0)
        return OrderQuotePublic(
            items=[],
            subtotal=0,
            discount=0,
            shipping=shipping,
            tax=tax,
            total=total,
            payment_method=PAYMENT_METHOD,
        )
    lines = [_line_from_cart(item) for item in cart.items]
    return _quote_from_lines(lines)


def create_order(db: Session, user: User, data: OrderCreate) -> OrderPublic:
    if data.customer.email != user.email:
        raise APIError(status_code=422, detail="Email must match the account")
    try:
        order_id = _place(db, user, data)
        db.commit()
    except APIError:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise APIError(status_code=409, detail="The order could not be placed")
    return _present(db, order_id)


def list_orders(db: Session, user: User, *, page: int, page_size: int) -> OrderPage:
    filters = [] if user.role == UserRole.admin else [Order.user_id == user.id]
    total = db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    orders = db.scalars(
        select(Order)
        .where(*filters)
        .order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .options(*_order_options())
    ).all()
    return OrderPage(
        items=[_present_order(order) for order in orders],
        page=page,
        page_size=page_size,
        total=total,
    )


def update_order_status(db: Session, order_id: uuid.UUID, status: OrderStatus) -> OrderPublic:
    order = db.get(Order, order_id)
    if order is None:
        raise APIError(status_code=404, detail="Order not found")
    order.status = status
    db.commit()
    return _present(db, order_id)


def get_order(db: Session, user: User, order_id: uuid.UUID) -> OrderPublic:
    order = db.scalar(select(Order).where(Order.id == order_id).options(*_order_options()))
    if order is None or (user.role != UserRole.admin and order.user_id != user.id):
        raise APIError(status_code=404, detail="Order not found")
    return _present_order(order)


def _place(db: Session, user: User, data: OrderCreate) -> uuid.UUID:
    cart = _active_cart(db, user)
    if cart is None or not cart.items:
        raise APIError(status_code=409, detail="The cart is empty")

    product_ids = sorted({item.product_id for item in cart.items})
    variant_ids = sorted({item.variant_id for item in cart.items if item.variant_id is not None})
    products = {product_id: _lock_product(db, product_id) for product_id in product_ids}
    variants = {variant_id: _lock_variant(db, variant_id) for variant_id in variant_ids}

    prepared: list[tuple[CartItem, Product, ProductVariant | None, OrderLinePublic]] = []
    for item in cart.items:
        product = products.get(item.product_id)
        variant = variants.get(item.variant_id) if item.variant_id is not None else None
        _assert_purchasable(product, variant, item.variant_id)
        assert product is not None
        _assert_stock(product, variant, item.quantity)
        line = _line_from_locked(product, variant, item.quantity)
        prepared.append((item, product, variant, line))

    subtotal, discount, goods_total = quote_totals(
        [(line.line_subtotal, line.line_total) for *_rest, line in prepared]
    )
    shipping, tax, total = fulfillment_charges(goods_total)
    billing = _new_address(user, data.customer, data.billing)
    shipping_address = billing if data.shipping_same_as_billing or data.shipping is None else _new_address(
        user,
        data.customer,
        data.shipping,
    )
    db.add(billing)
    if shipping_address is not billing:
        db.add(shipping_address)
    db.flush()

    order = Order(
        user_id=user.id,
        billing_address_id=billing.id,
        shipping_address_id=shipping_address.id,
        order_number=_order_number(),
        customer_name=data.customer.name,
        customer_email=data.customer.email,
        customer_phone=data.customer.phone,
        status=OrderStatus.pending,
        subtotal_paise=subtotal,
        discount_paise=discount,
        shipping_paise=shipping,
        tax_paise=tax,
        total_paise=total,
    )
    db.add(order)
    db.flush()
    for _item, product, variant, line in prepared:
        db.add(
            OrderItem(
                order_id=order.id,
                variant_id=variant.id if variant is not None else None,
                product_name=line.name,
                variant_name=line.variant_name,
                sku=line.sku,
                quantity=line.quantity,
                list_price_paise=line.list_price,
                unit_price_paise=line.unit_price,
            )
        )
        if variant is not None:
            variant.stock_qty -= line.quantity
        else:
            product.stock_quantity -= line.quantity
    attach_payment(db, order, data.payment_method)
    cart.status = CartStatus.converted
    return order.id


def _active_cart(db: Session, user: User) -> Cart | None:
    return db.scalar(
        select(Cart)
        .where(Cart.user_id == user.id, Cart.status == CartStatus.active)
        .options(
            selectinload(Cart.items).selectinload(CartItem.product).selectinload(Product.variants),
            selectinload(Cart.items).selectinload(CartItem.variant),
        )
    )


def _line_from_cart(item: CartItem) -> OrderLinePublic:
    product = item.product
    variant = item.variant
    active = [entry for entry in product.variants if entry.is_active]
    if product.status != RecordStatus.active or (active and variant is None) or (not active and variant is not None):
        raise APIError(status_code=409, detail="A product in the cart is no longer available")
    if variant is not None and (not variant.is_active or variant.product_id != product.id):
        raise APIError(status_code=409, detail="A product in the cart is no longer available")
    _assert_stock(product, variant, item.quantity)
    return _line_from_locked(product, variant, item.quantity)


def _line_from_locked(product: Product, variant: ProductVariant | None, quantity: int) -> OrderLinePublic:
    if variant is not None:
        list_price = variant.price_paise
        sale_price = variant.sale_price_paise
        sku = variant.sku
        variant_name = variant.name
    else:
        list_price = product.price_paise
        sale_price = product.sale_price_paise
        sku = product.sku
        variant_name = None
    unit_price, line_subtotal, line_discount, line_total, list_price = quote_line(list_price, sale_price, quantity)
    return OrderLinePublic(
        name=product.name,
        variant_name=variant_name,
        sku=sku,
        quantity=quantity,
        list_price=list_price,
        unit_price=unit_price,
        line_subtotal=line_subtotal,
        line_discount=line_discount,
        line_total=line_total,
    )


def _quote_from_lines(lines: list[OrderLinePublic]) -> OrderQuotePublic:
    subtotal, discount, goods_total = quote_totals([(line.line_subtotal, line.line_total) for line in lines])
    shipping, tax, total = fulfillment_charges(goods_total)
    return OrderQuotePublic(
        items=lines,
        subtotal=subtotal,
        discount=discount,
        shipping=shipping,
        tax=tax,
        total=total,
        payment_method=PAYMENT_METHOD,
    )


def _lock_product(db: Session, product_id: uuid.UUID) -> Product | None:
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        return None
    db.expire(product, ["variants"])
    db.refresh(product)
    return product


def _lock_variant(db: Session, variant_id: uuid.UUID) -> ProductVariant | None:
    variant = db.scalar(select(ProductVariant).where(ProductVariant.id == variant_id).with_for_update())
    if variant is None:
        return None
    db.refresh(variant)
    return variant


def _assert_purchasable(
    product: Product | None,
    variant: ProductVariant | None,
    variant_id: uuid.UUID | None,
) -> None:
    if product is None or product.status != RecordStatus.active:
        raise APIError(status_code=409, detail="A product in the cart is no longer available")
    active = [entry for entry in product.variants if entry.is_active]
    if (active and variant_id is None) or (not active and variant_id is not None):
        raise APIError(status_code=409, detail="A product in the cart is no longer available")
    if variant_id is not None and (variant is None or not variant.is_active or variant.product_id != product.id):
        raise APIError(status_code=409, detail="A product in the cart is no longer available")


def _assert_stock(product: Product, variant: ProductVariant | None, quantity: int) -> None:
    available = variant.stock_qty if variant is not None else product.stock_quantity
    if quantity > available:
        raise APIError(status_code=409, detail="Not enough stock")


def _new_address(user: User, customer: CustomerInput, address: AddressInput) -> Address:
    return Address(
        user_id=user.id,
        recipient_name=customer.name,
        phone=customer.phone,
        line1=address.address,
        city=address.city,
        state=address.state,
        postal_code=address.postal_code,
        country=address.country,
        is_default=False,
    )


def _order_number() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"SM{stamp}{uuid.uuid4().hex[:8].upper()}"


def _present(db: Session, order_id: uuid.UUID) -> OrderPublic:
    order = db.scalar(select(Order).where(Order.id == order_id).options(*_order_options()))
    if order is None:
        raise APIError(status_code=404, detail="Order not found")
    return _present_order(order)


def _present_order(order: Order) -> OrderPublic:
    if not order.payments or order.billing_address is None or order.shipping_address is None:
        raise APIError(status_code=404, detail="Order not found")
    payment = max(order.payments, key=lambda row: row.created_at)
    lines = [_line_from_order_item(item) for item in order.items]
    return OrderPublic(
        id=order.id,
        order_number=order.order_number,
        status=order.status.value.upper(),  # type: ignore[arg-type]
        payment_status=payment.status.value.upper(),  # type: ignore[arg-type]
        payment_method=payment.payment_method,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        customer_phone=order.customer_phone,
        billing_address=_address_public(order.billing_address),
        shipping_address=_address_public(order.shipping_address),
        items=lines,
        subtotal=order.subtotal_paise,
        discount=order.discount_paise,
        shipping=order.shipping_paise,
        tax=order.tax_paise,
        total=order.total_paise,
        created_at=order.created_at,
    )


def _line_from_order_item(item: OrderItem) -> OrderLinePublic:
    _unit_price, line_subtotal, line_discount, line_total, list_price = quote_line(
        item.list_price_paise,
        item.unit_price_paise,
        item.quantity,
    )
    return OrderLinePublic(
        name=item.product_name,
        variant_name=item.variant_name,
        sku=item.sku,
        quantity=item.quantity,
        list_price=list_price,
        unit_price=item.unit_price_paise,
        line_subtotal=line_subtotal,
        line_discount=line_discount,
        line_total=line_total,
    )


def _address_public(address: Address) -> AddressPublic:
    return AddressPublic(
        address=address.line1,
        city=address.city,
        state=address.state,
        postal_code=address.postal_code,
        country=address.country,
    )


def _order_options():
    return (
        selectinload(Order.items),
        selectinload(Order.payments),
        selectinload(Order.billing_address),
        selectinload(Order.shipping_address),
    )
