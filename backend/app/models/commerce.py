import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import (
    CartStatus,
    DiscountType,
    OrderStatus,
    PaymentStatus,
    pg_enum,
)


class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"
    __table_args__ = (
        CheckConstraint(
            "(discount_type = 'percent' AND discount_value BETWEEN 1 AND 100) "
            "OR (discount_type = 'fixed' AND discount_value > 0)",
            name="discount_value_valid",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    discount_type: Mapped[DiscountType] = mapped_column(
        pg_enum(DiscountType, "discount_type"),
        nullable=False,
    )
    discount_value: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    orders: Mapped[list["Order"]] = relationship(back_populates="coupon")


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"
    __table_args__ = (
        Index(
            "uq_carts_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[CartStatus] = mapped_column(
        pg_enum(CartStatus, "cart_status"),
        nullable=False,
        default=CartStatus.active,
        server_default=CartStatus.active.value,
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="carts")
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
    )


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        Index("ix_cart_items_variant_id", "variant_id"),
        Index("ix_cart_items_product_id", "product_id"),
        Index(
            "uq_cart_items_variant",
            "cart_id",
            "variant_id",
            unique=True,
            postgresql_where=text("variant_id IS NOT NULL"),
        ),
        Index(
            "uq_cart_items_base_product",
            "cart_id",
            "product_id",
            unique=True,
            postgresql_where=text("variant_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    cart_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
    )
    quantity: Mapped[int] = mapped_column(nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="cart_items")
    variant: Mapped["ProductVariant | None"] = relationship(back_populates="cart_items")


class Wishlist(Base, TimestampMixin):
    __tablename__ = "wishlists"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="wishlist")
    items: Mapped[list["WishlistItem"]] = relationship(
        back_populates="wishlist",
        cascade="all, delete-orphan",
    )


class WishlistItem(Base, TimestampMixin):
    __tablename__ = "wishlist_items"
    __table_args__ = (
        UniqueConstraint("wishlist_id", "product_id", name="uq_wishlist_items_product"),
        Index("ix_wishlist_items_product_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    wishlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wishlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    wishlist: Mapped[Wishlist] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="wishlist_items")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("subtotal_paise >= 0", name="subtotal_non_negative"),
        CheckConstraint("discount_paise >= 0", name="discount_non_negative"),
        CheckConstraint("discount_paise <= subtotal_paise", name="discount_not_above_subtotal"),
        CheckConstraint("shipping_paise >= 0", name="shipping_non_negative"),
        CheckConstraint("tax_paise >= 0", name="tax_non_negative"),
        CheckConstraint("total_paise >= 0", name="total_non_negative"),
        CheckConstraint(
            "total_paise = subtotal_paise - discount_paise + shipping_paise + tax_paise",
            name="total_equation",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    billing_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("addresses.id", ondelete="SET NULL"),
        index=True,
    )
    shipping_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("addresses.id", ondelete="SET NULL"),
        index=True,
    )
    coupon_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("coupons.id", ondelete="SET NULL"),
        index=True,
    )
    order_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"),
        nullable=False,
        default=OrderStatus.pending,
        server_default=OrderStatus.pending.value,
        index=True,
    )
    subtotal_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    shipping_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    tax_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)

    user: Mapped["User"] = relationship(back_populates="orders")
    billing_address: Mapped["Address | None"] = relationship(
        back_populates="billed_orders",
        foreign_keys=[billing_address_id],
    )
    shipping_address: Mapped["Address | None"] = relationship(
        back_populates="orders",
        foreign_keys=[shipping_address_id],
    )
    coupon: Mapped[Coupon | None] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price_paise >= 0", name="unit_price_non_negative"),
        CheckConstraint("list_price_paise >= 0", name="list_price_non_negative"),
        CheckConstraint("unit_price_paise <= list_price_paise", name="unit_price_not_above_list"),
        Index("ix_order_items_variant_id", "variant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL"),
    )
    product_name: Mapped[str] = mapped_column(String(180), nullable=False)
    variant_name: Mapped[str | None] = mapped_column(String(120))
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    list_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    variant: Mapped["ProductVariant | None"] = relationship(back_populates="order_items")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_paise >= 0", name="amount_non_negative"),
        CheckConstraint("char_length(currency) = 3", name="currency_code"),
        Index(
            "uq_payments_transaction_id",
            "transaction_id",
            unique=True,
            postgresql_where=text("transaction_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'INR'"))
    provider: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'manual'"))
    transaction_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"),
        nullable=False,
        default=PaymentStatus.pending,
        server_default=PaymentStatus.pending.value,
        index=True,
    )
    payment_method: Mapped[str] = mapped_column("method", String(32), nullable=False)

    order: Mapped[Order] = relationship(back_populates="payments")
