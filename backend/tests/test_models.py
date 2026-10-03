from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.db.base import Base

EXPECTED_TABLES = {
    "addresses",
    "cart_items",
    "carts",
    "categories",
    "contact_enquiries",
    "coupons",
    "event_enquiries",
    "event_service_images",
    "event_services",
    "order_items",
    "orders",
    "payments",
    "product_images",
    "product_variants",
    "products",
    "reviews",
    "revoked_tokens",
    "travel_enquiries",
    "travel_package_images",
    "travel_packages",
    "users",
    "wishlist_items",
    "wishlists",
}


def test_expected_tables_are_registered() -> None:
    configure_mappers()
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_every_relationship_is_bidirectional() -> None:
    configure_mappers()
    for mapper in Base.registry.mappers:
        for prop in mapper.relationships:
            assert prop.back_populates, f"{mapper.class_.__name__}.{prop.key} has no reverse"
            reverse = prop.mapper.relationships[prop.back_populates]
            assert reverse.mapper.class_ is mapper.class_
            assert reverse.back_populates == prop.key


def test_foreign_keys_are_indexed() -> None:
    indexed: dict[str, set[str]] = {}
    for table in Base.metadata.tables.values():
        columns: set[str] = set()
        for index in table.indexes:
            columns.update(column.name for column in index.columns)
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint):
                columns.update(column.name for column in constraint.columns)
        indexed[table.name] = columns

    missing: list[str] = []
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            if foreign_key.parent.name not in indexed[table.name]:
                missing.append(f"{table.name}.{foreign_key.parent.name}")

    assert missing == []
