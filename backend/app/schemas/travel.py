import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import EnquiryStatus, RecordStatus, TravelCategory
from app.services.storage.validate import clean_image_reference

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _required_text(value: str, message: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError(message)
    return cleaned


def _clean_phone(value: str) -> str:
    cleaned = "".join(character for character in value if character.isdigit() or character == "+")
    digits = cleaned[1:] if cleaned.startswith("+") else cleaned
    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        raise ValueError("Enter a valid phone number")
    return cleaned


class TravelImageWrite(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    alt_text: str | None = Field(default=None, max_length=180)
    sort_order: int = Field(default=0, ge=0, le=1000)

    @field_validator("url")
    @classmethod
    def clean_url(cls, value: str) -> str:
        return clean_image_reference(value)

    @field_validator("alt_text")
    @classmethod
    def clean_alt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class TravelPackageWrite(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    slug: str = Field(min_length=1, max_length=180)
    category: TravelCategory
    destination: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=80)
    duration: int = Field(ge=1, le=365)
    starting_price: int = Field(ge=0)
    description: str = Field(min_length=1, max_length=8000)
    itinerary: str = Field(default="", max_length=8000)
    accommodation: str = Field(default="", max_length=8000)
    transportation: str = Field(default="", max_length=8000)
    activities: str = Field(default="", max_length=8000)
    inclusions: str = Field(default="", max_length=8000)
    exclusions: str = Field(default="", max_length=8000)
    images: list[TravelImageWrite] = Field(default_factory=list, max_length=12)
    status: RecordStatus = RecordStatus.draft
    featured: bool = False

    @field_validator("title", "destination", "country")
    @classmethod
    def clean_required(cls, value: str) -> str:
        return _required_text(value, "This field is required")

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str) -> str:
        slug = value.strip().lower()
        if not SLUG_PATTERN.fullmatch(slug):
            raise ValueError("Slug must use lowercase letters, numbers, and hyphens")
        return slug

    @field_validator("description", "itinerary", "accommodation", "transportation", "activities", "inclusions", "exclusions")
    @classmethod
    def clean_body(cls, value: str) -> str:
        return value.strip()


class TravelImagePublic(BaseModel):
    id: uuid.UUID
    url: str
    alt_text: str | None
    sort_order: int


class TravelPackagePublic(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    category: TravelCategory
    destination: str
    country: str
    duration: int
    starting_price: int
    description: str
    itinerary: str
    accommodation: str
    transportation: str
    activities: str
    inclusions: str
    exclusions: str
    images: list[TravelImagePublic]
    status: RecordStatus
    featured: bool


class TravelPackagePage(BaseModel):
    items: list[TravelPackagePublic]
    page: int
    page_size: int
    total: int


class TravelEnquiryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=20)
    destination: str = Field(min_length=1, max_length=120)
    travel_date: date
    travelers: int = Field(ge=1, le=200)
    budget: int = Field(ge=0)
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("name", "destination")
    @classmethod
    def clean_required(cls, value: str) -> str:
        return _required_text(value, "This field is required")

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str) -> str:
        return _clean_phone(value)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message is required")
        return cleaned

    @field_validator("travel_date")
    @classmethod
    def date_not_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Travel date cannot be in the past")
        return value


class TravelEnquiryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EnquiryStatus


class TravelEnquiryPublic(BaseModel):
    id: uuid.UUID
    package_id: uuid.UUID | None
    name: str
    email: EmailStr
    phone: str
    destination: str
    travel_date: date
    travelers: int
    budget: int
    message: str
    status: EnquiryStatus
    created_at: datetime


class TravelEnquiryPage(BaseModel):
    items: list[TravelEnquiryPublic]
    page: int
    page_size: int
    total: int
