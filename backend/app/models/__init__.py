"""Import models so SQLAlchemy registers them on the shared metadata."""

from app.models.catalog import Category, Product, ProductImage, ProductVariant, Review
from app.models.commerce import (
    Cart,
    CartItem,
    Coupon,
    Order,
    OrderItem,
    Payment,
    Wishlist,
    WishlistItem,
)
from app.models.enquiries import (
    ContactEnquiry,
    EventEnquiry,
    EventService,
    EventServiceImage,
    TravelEnquiry,
    TravelPackage,
    TravelPackageImage,
)
from app.models.identity import Address, User
from app.models.revoked_token import RevokedToken

__all__ = [
    "Address",
    "Cart",
    "CartItem",
    "Category",
    "ContactEnquiry",
    "Coupon",
    "EventEnquiry",
    "EventService",
    "EventServiceImage",
    "Order",
    "OrderItem",
    "Payment",
    "Product",
    "ProductImage",
    "ProductVariant",
    "RevokedToken",
    "Review",
    "TravelEnquiry",
    "TravelPackage",
    "TravelPackageImage",
    "User",
    "Wishlist",
    "WishlistItem",
]
