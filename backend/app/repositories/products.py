import uuid

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Product, ProductVariant
from app.models.enums import RecordStatus


class ProductRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, product_id: uuid.UUID) -> Product | None:
        statement = (
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.category),
                selectinload(Product.variants),
                selectinload(Product.images),
            )
        )
        return self.db.scalar(statement)

    def slug_taken(self, slug: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        statement = select(Product.id).where(Product.slug == slug)
        if exclude_id is not None:
            statement = statement.where(Product.id != exclude_id)
        return self.db.scalar(statement) is not None

    def sku_taken(self, sku: str, *, exclude_product_id: uuid.UUID | None = None) -> bool:
        product_statement = select(Product.id).where(Product.sku == sku)
        variant_statement = select(ProductVariant.id).where(ProductVariant.sku == sku)
        if exclude_product_id is not None:
            product_statement = product_statement.where(Product.id != exclude_product_id)
            variant_statement = variant_statement.where(ProductVariant.product_id != exclude_product_id)
        return self.db.scalar(product_statement) is not None or self.db.scalar(variant_statement) is not None

    def list_products(
        self,
        *,
        active_only: bool,
        status: RecordStatus | None,
        category_ids: set[uuid.UUID] | None,
        search: str | None,
        min_price: int | None,
        max_price: int | None,
        available: bool | None,
        sort: str,
        offset: int,
        limit: int,
    ) -> tuple[list[Product], int]:
        conditions = self._conditions(
            active_only=active_only,
            status=status,
            category_ids=category_ids,
            search=search,
            min_price=min_price,
            max_price=max_price,
            available=available,
        )
        total = int(self.db.scalar(select(func.count()).select_from(Product).where(*conditions)) or 0)
        statement = (
            select(Product)
            .where(*conditions)
            .options(
                selectinload(Product.category),
                selectinload(Product.variants),
                selectinload(Product.images),
            )
            .order_by(*self._order(sort))
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(statement).unique()), total

    def _conditions(
        self,
        *,
        active_only: bool,
        status: RecordStatus | None,
        category_ids: set[uuid.UUID] | None,
        search: str | None,
        min_price: int | None,
        max_price: int | None,
        available: bool | None,
    ) -> list[object]:
        conditions: list[object] = []
        if active_only:
            conditions.append(Product.status == RecordStatus.active)
        elif status is not None:
            conditions.append(Product.status == status)
        if category_ids is not None:
            conditions.append(Product.category_id.in_(category_ids))
        if search:
            conditions.append(self._search(search))
        if min_price is not None or max_price is not None:
            conditions.append(self._price_match(min_price, max_price))
        if available is not None:
            in_stock = self._in_stock()
            conditions.append(in_stock if available else ~in_stock)
        return conditions

    def _search(self, search: str) -> object:
        term = f"%{self._escape_like(search.strip())}%"
        variant_match = exists(
            select(ProductVariant.id).where(
                ProductVariant.product_id == Product.id,
                or_(
                    ProductVariant.sku.ilike(term, escape="\\"),
                    ProductVariant.name.ilike(term, escape="\\"),
                ),
            )
        )
        return or_(
            Product.name.ilike(term, escape="\\"),
            Product.description.ilike(term, escape="\\"),
            Product.brand.ilike(term, escape="\\"),
            Product.sku.ilike(term, escape="\\"),
            variant_match,
        )

    def _price_match(self, min_price: int | None, max_price: int | None) -> object:
        product_price = func.coalesce(Product.sale_price_paise, Product.price_paise)
        variant_price = func.coalesce(ProductVariant.sale_price_paise, ProductVariant.price_paise)
        product_clause = self._range(product_price, min_price, max_price)
        variant_match = exists(
            select(ProductVariant.id).where(
                ProductVariant.product_id == Product.id,
                ProductVariant.is_active.is_(True),
                self._range(variant_price, min_price, max_price),
            )
        )
        return or_(product_clause, variant_match)

    def _in_stock(self) -> object:
        variant_stock = exists(
            select(ProductVariant.id).where(
                ProductVariant.product_id == Product.id,
                ProductVariant.is_active.is_(True),
                ProductVariant.stock_qty > 0,
            )
        )
        return or_(Product.stock_quantity > 0, variant_stock)

    @staticmethod
    def _range(column: object, min_price: int | None, max_price: int | None) -> object:
        if min_price is not None and max_price is not None:
            return column.between(min_price, max_price)
        if min_price is not None:
            return column >= min_price
        return column <= max_price

    @staticmethod
    def _order(sort: str) -> tuple[object, ...]:
        price = func.coalesce(Product.sale_price_paise, Product.price_paise)
        options = {
            "name": (Product.name.asc(), Product.id.asc()),
            "-name": (Product.name.desc(), Product.id.asc()),
            "price": (price.asc(), Product.id.asc()),
            "-price": (price.desc(), Product.id.asc()),
            "created_at": (Product.created_at.asc(), Product.id.asc()),
            "-created_at": (Product.created_at.desc(), Product.id.asc()),
            "featured": (Product.is_featured.desc(), Product.created_at.desc(), Product.id.asc()),
        }
        return options[sort]

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
