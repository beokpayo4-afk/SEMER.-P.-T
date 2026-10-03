import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import EnquiryStatus, EventCategory, RecordStatus
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


class EventImageWrite(BaseModel):
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


class EventServiceWrite(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    slug: str = Field(min_length=1, max_length=180)
    category: EventCategory
    description: str = Field(min_length=1, max_length=8000)
    services: str = Field(default="", max_length=8000)
    images: list[EventImageWrite] = Field(default_factory=list, max_length=12)
    status: RecordStatus = RecordStatus.draft
    featured: bool = False

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return _required_text(value, "Title is required")

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str) -> str:
        slug = value.strip().lower()
        if not SLUG_PATTERN.fullmatch(slug):
            raise ValueError("Slug must use lowercase letters, numbers, and hyphens")
        return slug

    @field_validator("description", "services")
    @classmethod
    def clean_body(cls, value: str) -> str:
        return value.strip()


class EventImagePublic(BaseModel):
    id: uuid.UUID
    url: str
    alt_text: str | None
    sort_order: int


class EventServicePublic(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    category: EventCategory
    description: str
    services: str
    images: list[EventImagePublic]
    status: RecordStatus
    featured: bool


class EventServicePage(BaseModel):
    items: list[EventServicePublic]
    page: int
    page_size: int
    total: int


class EventEnquiryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=20)
    event_type: EventCategory
    event_date: date
    location: str = Field(min_length=1, max_length=180)
    expected_guests: int = Field(ge=1, le=20000)
    budget: int = Field(ge=0)
    requirements: str = Field(min_length=1, max_length=4000)
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("name", "location")
    @classmethod
    def clean_required(cls, value: str) -> str:
        return _required_text(value, "This field is required")

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str) -> str:
        return _clean_phone(value)

    @field_validator("requirements", "message")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field is required")
        return cleaned

    @field_validator("event_date")
    @classmethod
    def date_not_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Event date cannot be in the past")
        return value


class EventEnquiryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EnquiryStatus | None = None
    internal_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("internal_notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def require_a_change(self) -> "EventEnquiryUpdate":
        if self.status is None and self.internal_notes is None:
            raise ValueError("Provide a status or a note")
        return self


class EventEnquirySubmitted(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID | None
    name: str
    email: EmailStr
    phone: str
    event_type: EventCategory
    event_date: date
    location: str
    expected_guests: int
    budget: int
    requirements: str
    message: str
    status: EnquiryStatus
    created_at: datetime


class EventEnquiryAdmin(EventEnquirySubmitted):
    internal_notes: str


class EventEnquiryPage(BaseModel):
    items: list[EventEnquiryAdmin]
    page: int
    page_size: int
    total: int
