import uuid
from datetime import date

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import (
    EnquiryStatus,
    EventCategory,
    PackageCategory,
    PackageType,
    RecordStatus,
    TravelCategory,
    pg_enum,
)


class TravelPackage(Base, TimestampMixin):
    __tablename__ = "travel_packages"
    __table_args__ = (
        CheckConstraint("duration_days > 0", name="duration_positive"),
        CheckConstraint("price_from_paise >= 0", name="price_non_negative"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    category: Mapped[TravelCategory] = mapped_column(
        pg_enum(TravelCategory, "travel_category"),
        nullable=False,
        index=True,
    )
    package_type: Mapped[PackageType] = mapped_column(
        pg_enum(PackageType, "package_type"),
        nullable=False,
        default=PackageType.domestic,
        server_default=PackageType.domestic.value,
        index=True,
    )
    package_category: Mapped[PackageCategory | None] = mapped_column(
        pg_enum(PackageCategory, "package_category"),
        index=True,
    )
    destination: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(80), nullable=False)
    duration_days: Mapped[int] = mapped_column(nullable=False)
    price_from_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    itinerary: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    accommodation: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    transportation: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    activities: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    inclusions: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    exclusions: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    romantic_highlights: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    hotel_category: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    room_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    couple_experiences: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    honeymoon_inclusions: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )
    status: Mapped[RecordStatus] = mapped_column(
        pg_enum(RecordStatus, "record_status"),
        nullable=False,
        default=RecordStatus.draft,
        server_default=RecordStatus.draft.value,
        index=True,
    )

    images: Mapped[list["TravelPackageImage"]] = relationship(
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="TravelPackageImage.sort_order",
    )
    enquiries: Mapped[list["TravelEnquiry"]] = relationship(back_populates="package")


class TravelPackageImage(Base, TimestampMixin):
    __tablename__ = "travel_package_images"

    id: Mapped[uuid.UUID] = uuid_pk()
    package_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("travel_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(180))
    sort_order: Mapped[int] = mapped_column(nullable=False, server_default="0")

    package: Mapped[TravelPackage] = relationship(back_populates="images")


class TravelEnquiry(Base, TimestampMixin):
    __tablename__ = "travel_enquiries"
    __table_args__ = (
        CheckConstraint("travelers > 0", name="travelers_positive"),
        CheckConstraint("budget_paise >= 0", name="budget_non_negative"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    travel_package_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("travel_packages.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    destination: Mapped[str] = mapped_column(String(120), nullable=False)
    travel_date: Mapped[date] = mapped_column(Date, nullable=False)
    travelers: Mapped[int] = mapped_column(nullable=False)
    budget_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EnquiryStatus] = mapped_column(
        pg_enum(EnquiryStatus, "enquiry_status"),
        nullable=False,
        default=EnquiryStatus.new,
        server_default=EnquiryStatus.new.value,
        index=True,
    )

    user: Mapped["User | None"] = relationship(back_populates="travel_enquiries")
    package: Mapped[TravelPackage | None] = relationship(back_populates="enquiries")


class EventService(Base, TimestampMixin):
    __tablename__ = "event_services"
    __table_args__ = (
        CheckConstraint(
            "price_from_paise IS NULL OR price_from_paise >= 0",
            name="price_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    category: Mapped[EventCategory] = mapped_column(
        pg_enum(EventCategory, "event_category"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    services: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    price_from_paise: Mapped[int | None] = mapped_column(BigInteger)
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )
    status: Mapped[RecordStatus] = mapped_column(
        pg_enum(RecordStatus, "record_status"),
        nullable=False,
        default=RecordStatus.draft,
        server_default=RecordStatus.draft.value,
        index=True,
    )

    images: Mapped[list["EventServiceImage"]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
        order_by="EventServiceImage.sort_order",
    )
    enquiries: Mapped[list["EventEnquiry"]] = relationship(back_populates="service")


class EventServiceImage(Base, TimestampMixin):
    __tablename__ = "event_service_images"

    id: Mapped[uuid.UUID] = uuid_pk()
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event_services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(180))
    sort_order: Mapped[int] = mapped_column(nullable=False, server_default="0")

    service: Mapped[EventService] = relationship(back_populates="images")


class EventEnquiry(Base, TimestampMixin):
    __tablename__ = "event_enquiries"
    __table_args__ = (
        CheckConstraint("expected_guests > 0", name="guests_positive"),
        CheckConstraint("budget_paise >= 0", name="budget_non_negative"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    event_service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("event_services.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    event_type: Mapped[EventCategory] = mapped_column(
        pg_enum(EventCategory, "event_category"),
        nullable=False,
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str] = mapped_column(String(180), nullable=False)
    expected_guests: Mapped[int] = mapped_column(nullable=False)
    budget_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requirements: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    internal_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    status: Mapped[EnquiryStatus] = mapped_column(
        pg_enum(EnquiryStatus, "enquiry_status"),
        nullable=False,
        default=EnquiryStatus.new,
        server_default=EnquiryStatus.new.value,
        index=True,
    )

    user: Mapped["User | None"] = relationship(back_populates="event_enquiries")
    service: Mapped[EventService | None] = relationship(back_populates="enquiries")


class ContactEnquiry(Base, TimestampMixin):
    __tablename__ = "contact_enquiries"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EnquiryStatus] = mapped_column(
        pg_enum(EnquiryStatus, "enquiry_status"),
        nullable=False,
        default=EnquiryStatus.new,
        server_default=EnquiryStatus.new.value,
        index=True,
    )
