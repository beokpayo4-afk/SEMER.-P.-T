import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import RecordStatus
from app.services.storage.validate import clean_image_reference

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _clean_slug(value: str) -> str:
    slug = value.strip().lower()
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("Slug must use lowercase letters, numbers, and hyphens")
    return slug


def _clean_sku(value: str) -> str:
    sku = value.strip()
    if not sku:
        raise ValueError("SKU is required")
    return sku


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=160)
    parent_id: uuid.UUID | None = None
    image_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Name is required")
        return cleaned

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str) -> str:
        return _clean_slug(value)

    @field_validator("image_url")
    @classmethod
    def clean_image(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return clean_image_reference(value)


class CategoryUpdate(CategoryCreate):
    pass


class CategoryPublic(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None
    image_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CategorySummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class VariantWrite(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    price: int = Field(ge=0, description="Price in paise")
    sale_price: int | None = Field(default=None, ge=0, description="Sale price in paise")
    stock_quantity: int = Field(default=0, ge=0)
    is_active: bool = True

    @field_validator("sku")
    @classmethod
    def clean_sku(cls, value: str) -> str:
        return _clean_sku(value)

    @model_validator(mode="after")
    def sale_not_above_price(self) -> "VariantWrite":
        if self.sale_price is not None and self.sale_price > self.price:
            raise ValueError("Sale price cannot be greater than price")
        return self


class ImageWrite(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    alt_text: str | None = Field(default=None, max_length=180)
    sort_order: int = 0
    variant_sku: str | None = Field(default=None, max_length=64)

    @field_validator("variant_sku")
    @classmethod
    def clean_variant_sku(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_sku(value)

    @field_validator("url")
    @classmethod
    def clean_url(cls, value: str) -> str:
        return clean_image_reference(value)


class ProductWrite(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    slug: str = Field(min_length=1, max_length=180)
    description: str = Field(min_length=1)
    price: int = Field(ge=0, description="Price in paise")
    sale_price: int | None = Field(default=None, ge=0, description="Sale price in paise")
    sku: str = Field(min_length=1, max_length=64)
    stock_quantity: int = Field(default=0, ge=0)
    category_id: uuid.UUID
    brand: str | None = Field(default=None, max_length=120)
    status: RecordStatus = RecordStatus.draft
    featured: bool = False
    images: list[ImageWrite] = Field(default_factory=list)
    variants: list[VariantWrite] = Field(default_factory=list)

    @field_validator("name", "brand")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str) -> str:
        return _clean_slug(value)

    @field_validator("sku")
    @classmethod
    def clean_sku(cls, value: str) -> str:
        return _clean_sku(value)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Description is required")
        return cleaned

    @model_validator(mode="after")
    def check_prices_and_skus(self) -> "ProductWrite":
        if self.sale_price is not None and self.sale_price > self.price:
            raise ValueError("Sale price cannot be greater than price")
        variants = self.variants or []
        images = self.images or []
        variant_skus = [variant.sku for variant in variants]
        if len(variant_skus) != len(set(variant_skus)):
            raise ValueError("Variant SKUs must be unique")
        if self.sku in variant_skus:
            raise ValueError("Product SKU must differ from variant SKUs")
        if self.images is not None and self.variants is not None:
            known = set(variant_skus)
            for image in images:
                if image.variant_sku is not None and image.variant_sku not in known:
                    raise ValueError("Image variant_sku does not match a variant")
        return self


class ProductUpdate(ProductWrite):
    images: list[ImageWrite] | None = None
    variants: list[VariantWrite] | None = None


class VariantPublic(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    price: int
    sale_price: int | None
    stock_quantity: int
    is_active: bool


class ImagePublic(BaseModel):
    id: uuid.UUID
    url: str
    alt_text: str | None
    sort_order: int
    variant_id: uuid.UUID | None


class ProductPublic(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str
    price: int
    sale_price: int | None
    sku: str
    stock_quantity: int
    category: CategorySummary
    brand: str | None
    status: RecordStatus
    featured: bool
    images: list[ImagePublic]
    variants: list[VariantPublic]
    rating_average: float | None = None
    review_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProductPage(BaseModel):
    items: list[ProductPublic]
    page: int
    page_size: int
    total: int
