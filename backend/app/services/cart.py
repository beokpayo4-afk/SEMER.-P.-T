import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import APIError
from app.models.catalog import Product, ProductImage, ProductVariant
from app.models.commerce import Cart, CartItem
from app.models.enums import CartStatus, RecordStatus
from app.models.identity import User
from app.schemas.cart import CartItemCreate, CartItemPublic, CartPublic
from app.services.pricing import quote_line, quote_totals


def get_cart(db: Session, user: User) -> CartPublic:
    return _present(db, _active_cart(db, user))


def add_item(db: Session, user: User, data: CartItemCreate) -> CartPublic:
    cart = _active_cart(db, user)
    product, variant = _purchasable(db, data.product_id, data.variant_id)
    item = _find_item(cart, product.id, variant.id if variant else None)
    quantity = data.quantity if item is None else item.quantity + data.quantity
    _assert_stock(product, variant, quantity)
    if item is None:
        item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            variant_id=variant.id if variant else None,
            quantity=quantity,
        )
        db.add(item)
    else:
        item.quantity = quantity
    db.commit()
    return _present(db, cart)


def update_item(db: Session, user: User, item_id: uuid.UUID, quantity: int) -> CartPublic:
    item = _owned_item(db, user, item_id)
    product, variant = _purchasable(db, item.product_id, item.variant_id)
    _assert_stock(product, variant, quantity)
    item.quantity = quantity
    db.commit()
    return _present(db, item.cart)


def remove_item(db: Session, user: User, item_id: uuid.UUID) -> None:
    item = _owned_item(db, user, item_id)
    db.delete(item)
    db.commit()


def clear_cart(db: Session, user: User) -> None:
    cart = _active_cart(db, user)
    for item in list(cart.items):
        db.delete(item)
    db.commit()


def _active_cart(db: Session, user: User) -> Cart:
    cart = db.scalar(
        select(Cart)
        .where(Cart.user_id == user.id, Cart.status == CartStatus.active)
        .options(*_cart_options())
    )
    if cart is not None:
        return cart
    cart = Cart(user_id=user.id, status=CartStatus.active)
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart


def _owned_item(db: Session, user: User, item_id: uuid.UUID) -> CartItem:
    item = db.scalar(
        select(CartItem)
        .join(Cart)
        .where(
            CartItem.id == item_id,
            Cart.user_id == user.id,
            Cart.status == CartStatus.active,
        )
        .options(selectinload(CartItem.cart))
    )
    if item is None:
        raise APIError(status_code=404, detail="Cart item not found")
    return item


def _purchasable(
    db: Session,
    product_id: uuid.UUID,
    variant_id: uuid.UUID | None,
) -> tuple[Product, ProductVariant | None]:
    product = db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants), selectinload(Product.images))
    )
    if product is None or product.status != RecordStatus.active:
        raise APIError(status_code=404, detail="Product not found")
    active_variants = [variant for variant in product.variants if variant.is_active]
    if active_variants and variant_id is None:
        raise APIError(status_code=422, detail="Choose a variant")
    if not active_variants and variant_id is not None:
        raise APIError(status_code=422, detail="This product has no variants")
    variant = None
    if variant_id is not None:
        variant = next((entry for entry in active_variants if entry.id == variant_id), None)
        if variant is None:
            raise APIError(status_code=404, detail="Variant not found")
    return product, variant


def _assert_stock(product: Product, variant: ProductVariant | None, quantity: int) -> None:
    available = variant.stock_qty if variant is not None else product.stock_quantity
    if quantity > available:
        raise APIError(status_code=409, detail="Not enough stock")


def _find_item(cart: Cart, product_id: uuid.UUID, variant_id: uuid.UUID | None) -> CartItem | None:
    for item in cart.items:
        if item.product_id == product_id and item.variant_id == variant_id:
            return item
    return None


def _present(db: Session, cart: Cart) -> CartPublic:
    stored = db.scalar(select(Cart).where(Cart.id == cart.id).options(*_cart_options()))
    if stored is None:
        raise APIError(status_code=404, detail="Cart not found")
    items: list[CartItemPublic] = []
    totals: list[tuple[int, int]] = []
    for item in stored.items:
        product = item.product
        variant = item.variant
        list_price = variant.price_paise if variant is not None else product.price_paise
        sale_price = variant.sale_price_paise if variant is not None else product.sale_price_paise
        unit_price, line_subtotal, line_discount, line_total, list_price = quote_line(
            list_price,
            sale_price,
            item.quantity,
        )
        stock = variant.stock_qty if variant is not None else product.stock_quantity
        items.append(
            CartItemPublic(
                id=item.id,
                product_id=product.id,
                variant_id=variant.id if variant is not None else None,
                name=product.name,
                variant_name=variant.name if variant is not None else None,
                sku=variant.sku if variant is not None else product.sku,
                image_url=_image_url(product.images, variant.id if variant is not None else None),
                quantity=item.quantity,
                stock_quantity=stock,
                list_price=list_price,
                unit_price=unit_price,
                line_subtotal=line_subtotal,
                line_discount=line_discount,
                line_total=line_total,
            )
        )
        totals.append((line_subtotal, line_total))
    subtotal, discount, total = quote_totals(totals)
    return CartPublic(id=stored.id, items=items, subtotal=subtotal, discount=discount, total=total)


def _image_url(images: list[ProductImage], variant_id: uuid.UUID | None) -> str | None:
    ordered = sorted(images, key=lambda image: image.sort_order)
    if variant_id is not None:
        matched = next((image for image in ordered if image.variant_id == variant_id), None)
        if matched is not None:
            return matched.url
    base = next((image for image in ordered if image.variant_id is None), None)
    if base is not None:
        return base.url
    return ordered[0].url if ordered else None


def _cart_options():
    return (
        selectinload(Cart.items).selectinload(CartItem.product).selectinload(Product.images),
        selectinload(Cart.items).selectinload(CartItem.variant),
    )
