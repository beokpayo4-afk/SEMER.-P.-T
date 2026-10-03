import enum

from sqlalchemy import Enum


class UserRole(str, enum.Enum):
    customer = "customer"
    admin = "admin"


class RecordStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class CartStatus(str, enum.Enum):
    active = "active"
    converted = "converted"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    refunded = "refunded"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


class DiscountType(str, enum.Enum):
    percent = "percent"
    fixed = "fixed"


class EnquiryStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    closed = "closed"


class TravelCategory(str, enum.Enum):
    domestic = "domestic"
    international = "international"
    holiday = "holiday"
    honeymoon = "honeymoon"
    customized = "customized"


class PackageType(str, enum.Enum):
    domestic = "domestic"
    international = "international"


class EventCategory(str, enum.Enum):
    wedding = "wedding"
    anniversary = "anniversary"
    private_party = "private_party"
    planning = "planning"
    decoration = "decoration"
    logistics = "logistics"


def pg_enum(enum_class: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )
