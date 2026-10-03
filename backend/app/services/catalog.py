import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.models.catalog import Category, Product, ProductImage, ProductVariant, Review
from app.models.enums import RecordStatus, UserRole
from app.models.identity import User
from app.repositories.categories import CategoryRepository
from app.repositories.products import ProductRepository
from app.schemas.catalog import (
    CategoryCreate,
    CategoryPublic,
    CategorySummary,
    CategoryUpdate,
    ImagePublic,
    ImageWrite,
    ProductPage,
    ProductPublic,
    ProductUpdate,
    ProductWrite,
    VariantPublic,
    VariantWrite,
)

SORTS = {"name", "-name", "price", "-price", "created_at", "-created_at", "featured"}


def _is_admin(user: User | None) -> bool:
    return user is not None and user.role == UserRole.admin


def category_public(category: Category) -> CategoryPublic:
    return CategoryPublic(
        id=category.id,
        name=category.name,
        slug=category.slug,
        parent_id=category.parent_id,
        image_url=category.image_url,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def review_stats(db: Session, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[float | None, int]]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(Review.product_id, func.avg(Review.rating), func.count(Review.id))
        .where(Review.product_id.in_(product_ids))
        .group_by(Review.product_id)
    ).all()
    return {product_id: (round(float(average), 1), int(count)) for product_id, average, count in rows}


def product_public(product: Product, stats: tuple[float | None, int] | None = None) -> ProductPublic:
    average, count = stats if stats is not None else (None, 0)
    return ProductPublic(
        id=product.id,
        name=product.name,
        slug=product.slug,
        description=product.description,
        price=product.price_paise,
        sale_price=product.sale_price_paise,
        sku=product.sku,
        stock_quantity=product.stock_quantity,
        category=CategorySummary(id=product.category.id, name=product.category.name, slug=product.category.slug),
        brand=product.brand,
        status=product.status,
        featured=product.is_featured,
        images=[
            ImagePublic(
                id=image.id,
                url=image.url,
                alt_text=image.alt_text,
                sort_order=image.sort_order,
                variant_id=image.variant_id,
            )
            for image in product.images
        ],
        variants=[
            VariantPublic(
                id=variant.id,
                sku=variant.sku,
                name=variant.name,
                price=variant.price_paise,
                sale_price=variant.sale_price_paise,
                stock_quantity=variant.stock_qty,
                is_active=variant.is_active,
            )
            for variant in product.variants
        ],
        rating_average=average,
        review_count=count,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _public_products(db: Session, products: list[Product]) -> list[ProductPublic]:
    stats = review_stats(db, [product.id for product in products])
    return [product_public(product, stats.get(product.id, (None, 0))) for product in products]


def list_categories(db: Session, viewer: User | None) -> list[CategoryPublic]:
    categories = CategoryRepository(db).list_categories(active_only=not _is_admin(viewer))
    return [category_public(category) for category in categories]


def get_category(db: Session, category_id: uuid.UUID, viewer: User | None) -> CategoryPublic:
    category = CategoryRepository(db).get(category_id)
    if category is None or (not category.is_active and not _is_admin(viewer)):
        raise APIError(status_code=404, detail="Category not found")
    return category_public(category)


def create_category(db: Session, data: CategoryCreate) -> CategoryPublic:
    repository = CategoryRepository(db)
    _assert_parent(repository, parent_id=data.parent_id, category_id=None)
    if repository.slug_taken(data.slug):
        raise APIError(status_code=409, detail="Slug is already in use")
    category = Category(
        name=data.name,
        slug=data.slug,
        parent_id=data.parent_id,
        image_url=data.image_url,
        is_active=data.is_active,
    )
    db.add(category)
    _commit(db)
    db.refresh(category)
    return category_public(category)


def update_category(db: Session, category_id: uuid.UUID, data: CategoryUpdate) -> CategoryPublic:
    repository = CategoryRepository(db)
    category = repository.get(category_id)
    if category is None:
        raise APIError(status_code=404, detail="Category not found")
    _assert_parent(repository, parent_id=data.parent_id, category_id=category_id)
    if repository.slug_taken(data.slug, exclude_id=category_id):
        raise APIError(status_code=409, detail="Slug is already in use")
    category.name = data.name
    category.slug = data.slug
    category.parent_id = data.parent_id
    category.image_url = data.image_url
    category.is_active = data.is_active
    _commit(db)
    db.refresh(category)
    return category_public(category)


def delete_category(db: Session, category_id: uuid.UUID) -> None:
    repository = CategoryRepository(db)
    category = repository.get(category_id)
    if category is None:
        raise APIError(status_code=404, detail="Category not found")
    if repository.child_count(category_id) or repository.product_count(category_id):
        raise APIError(status_code=409, detail="Category still has products or subcategories")
    db.delete(category)
    _commit(db)


def list_products(
    db: Session,
    *,
    viewer: User | None,
    category_id: uuid.UUID | None,
    search: str | None,
    min_price: int | None,
    max_price: int | None,
    available: bool | None,
    status: RecordStatus | None,
    page: int,
    page_size: int,
    sort: str,
) -> ProductPage:
    if sort not in SORTS:
        raise APIError(status_code=422, detail="Unsupported sort")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise APIError(status_code=422, detail="min_price cannot be greater than max_price")

    admin = _is_admin(viewer)
    category_ids = None
    if category_id is not None:
        categories = CategoryRepository(db)
        if categories.get(category_id) is None:
            raise APIError(status_code=404, detail="Category not found")
        category_ids = categories.descendant_ids(category_id)

    products, total = ProductRepository(db).list_products(
        active_only=not admin,
        status=status if admin else None,
        category_ids=category_ids,
        search=search,
        min_price=min_price,
        max_price=max_price,
        available=available,
        sort=sort,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return ProductPage(
        items=_public_products(db, products),
        page=page,
        page_size=page_size,
        total=total,
    )


def get_product(db: Session, product_id: uuid.UUID, viewer: User | None) -> ProductPublic:
    product = ProductRepository(db).get(product_id)
    if product is None or (product.status != RecordStatus.active and not _is_admin(viewer)):
        raise APIError(status_code=404, detail="Product not found")
    return _public_products(db, [product])[0]


def create_product(db: Session, data: ProductWrite) -> ProductPublic:
    _assert_category(db, data.category_id)
    _assert_skus_available(db, [data.sku, *[variant.sku for variant in data.variants]])
    if ProductRepository(db).slug_taken(data.slug):
        raise APIError(status_code=409, detail="Slug is already in use")
    product = Product(
        category_id=data.category_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        brand=data.brand,
        sku=data.sku,
        price_paise=data.price,
        sale_price_paise=data.sale_price,
        stock_quantity=data.stock_quantity,
        is_featured=data.featured,
        status=data.status,
    )
    _apply_variants(product, data.variants)
    db.add(product)
    db.flush()
    _apply_images(product, data.images)
    _commit(db)
    stored = ProductRepository(db).get(product.id)
    if stored is None:
        raise APIError(status_code=500, detail="Product could not be loaded")
    return _public_products(db, [stored])[0]


def update_product(db: Session, product_id: uuid.UUID, data: ProductUpdate) -> ProductPublic:
    repository = ProductRepository(db)
    product = repository.get(product_id)
    if product is None:
        raise APIError(status_code=404, detail="Product not found")
    _assert_category(db, data.category_id)
    skus = [data.sku]
    if data.variants is not None:
        skus.extend(variant.sku for variant in data.variants)
    _assert_skus_available(db, skus, exclude_product_id=product_id)
    if repository.slug_taken(data.slug, exclude_id=product_id):
        raise APIError(status_code=409, detail="Slug is already in use")

    try:
        product.category_id = data.category_id
        product.name = data.name
        product.slug = data.slug
        product.description = data.description
        product.brand = data.brand
        product.sku = data.sku
        product.price_paise = data.price
        product.sale_price_paise = data.sale_price
        product.stock_quantity = data.stock_quantity
        product.is_featured = data.featured
        product.status = data.status
        if data.variants is not None:
            product.variants.clear()
            db.flush()
            _apply_variants(product, data.variants)
            db.flush()
        if data.images is not None:
            product.images.clear()
            db.flush()
            _apply_images(product, data.images)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIError(status_code=409, detail="Product is in use and cannot be changed") from exc
    stored = repository.get(product_id)
    if stored is None:
        raise APIError(status_code=500, detail="Product could not be loaded")
    return _public_products(db, [stored])[0]


def update_stock(db: Session, product_id: uuid.UUID, stock_quantity: int) -> ProductPublic:
    product = ProductRepository(db).get(product_id)
    if product is None:
        raise APIError(status_code=404, detail="Product not found")
    product.stock_quantity = stock_quantity
    _commit(db)
    stored = ProductRepository(db).get(product_id)
    if stored is None:
        raise APIError(status_code=404, detail="Product not found")
    return _public_products(db, [stored])[0]


def delete_product(db: Session, product_id: uuid.UUID) -> None:
    product = ProductRepository(db).get(product_id)
    if product is None:
        raise APIError(status_code=404, detail="Product not found")
    db.delete(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIError(status_code=409, detail="Product is in use and cannot be deleted") from exc


def _assert_parent(repository: CategoryRepository, *, parent_id: uuid.UUID | None, category_id: uuid.UUID | None) -> None:
    if parent_id is None:
        return
    if category_id is not None and parent_id == category_id:
        raise APIError(status_code=422, detail="A category cannot be its own parent")
    parent = repository.get(parent_id)
    if parent is None:
        raise APIError(status_code=404, detail="Parent category not found")
    if category_id is not None and parent_id in repository.descendant_ids(category_id):
        raise APIError(status_code=422, detail="A category cannot be nested under its own child")


def _assert_category(db: Session, category_id: uuid.UUID) -> None:
    if CategoryRepository(db).get(category_id) is None:
        raise APIError(status_code=404, detail="Category not found")


def _assert_skus_available(db: Session, skus: list[str], *, exclude_product_id: uuid.UUID | None = None) -> None:
    repository = ProductRepository(db)
    for sku in skus:
        if repository.sku_taken(sku, exclude_product_id=exclude_product_id):
            raise APIError(status_code=409, detail="SKU is already in use")


def _apply_variants(product: Product, variants: list[VariantWrite]) -> None:
    for variant in variants:
        product.variants.append(
            ProductVariant(
                sku=variant.sku,
                name=variant.name,
                price_paise=variant.price,
                sale_price_paise=variant.sale_price,
                stock_qty=variant.stock_quantity,
                is_active=variant.is_active,
            )
        )


def _apply_images(product: Product, images: list[ImageWrite]) -> None:
    variants_by_sku = {variant.sku: variant for variant in product.variants}
    for image in images:
        variant = variants_by_sku.get(image.variant_sku) if image.variant_sku else None
        if image.variant_sku and variant is None:
            raise APIError(status_code=422, detail="Image variant_sku does not match a variant")
        product.images.append(
            ProductImage(
                url=image.url,
                alt_text=image.alt_text,
                sort_order=image.sort_order,
                variant_id=variant.id if variant is not None else None,
            )
        )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIError(status_code=409, detail="Catalog value is already in use") from exc
