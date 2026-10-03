import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Category, Product


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_categories(self, *, active_only: bool) -> list[Category]:
        statement = select(Category).order_by(Category.name)
        if active_only:
            statement = statement.where(Category.is_active.is_(True))
        return list(self.db.scalars(statement))

    def get(self, category_id: uuid.UUID) -> Category | None:
        return self.db.get(Category, category_id)

    def slug_taken(self, slug: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        statement = select(Category.id).where(Category.slug == slug)
        if exclude_id is not None:
            statement = statement.where(Category.id != exclude_id)
        return self.db.scalar(statement) is not None

    def child_count(self, category_id: uuid.UUID) -> int:
        statement = select(func.count()).select_from(Category).where(Category.parent_id == category_id)
        return int(self.db.scalar(statement) or 0)

    def product_count(self, category_id: uuid.UUID) -> int:
        statement = select(func.count()).select_from(Product).where(Product.category_id == category_id)
        return int(self.db.scalar(statement) or 0)

    def descendant_ids(self, category_id: uuid.UUID) -> set[uuid.UUID]:
        rows = self.db.execute(select(Category.id, Category.parent_id)).all()
        children: dict[uuid.UUID | None, list[uuid.UUID]] = {}
        for child_id, parent_id in rows:
            children.setdefault(parent_id, []).append(child_id)
        collected = {category_id}
        pending = [category_id]
        while pending:
            current = pending.pop()
            for child_id in children.get(current, []):
                if child_id not in collected:
                    collected.add(child_id)
                    pending.append(child_id)
        return collected
