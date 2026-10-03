"""allow product-level cart items

Revision ID: c4a8e1b27d03
Revises: 61ade43a7b98
Create Date: 2026-09-29 13:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4a8e1b27d03"
down_revision: Union[str, Sequence[str], None] = "61ade43a7b98"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cart_items", sa.Column("product_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE cart_items AS item
        SET product_id = variant.product_id
        FROM product_variants AS variant
        WHERE item.variant_id = variant.id
        """
    )
    op.alter_column("cart_items", "product_id", nullable=False)
    op.alter_column("cart_items", "variant_id", existing_type=sa.Uuid(), nullable=True)
    op.create_foreign_key(
        op.f("fk_cart_items_product_id_products"),
        "cart_items",
        "products",
        ["product_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_cart_items_product_id"), "cart_items", ["product_id"], unique=False)
    op.drop_constraint("uq_cart_items_cart_variant", "cart_items", type_="unique")
    op.create_index(
        "uq_cart_items_variant",
        "cart_items",
        ["cart_id", "variant_id"],
        unique=True,
        postgresql_where=sa.text("variant_id IS NOT NULL"),
    )
    op.create_index(
        "uq_cart_items_base_product",
        "cart_items",
        ["cart_id", "product_id"],
        unique=True,
        postgresql_where=sa.text("variant_id IS NULL"),
    )


def downgrade() -> None:
    op.execute("DELETE FROM cart_items WHERE variant_id IS NULL")
    op.drop_index("uq_cart_items_base_product", table_name="cart_items")
    op.drop_index("uq_cart_items_variant", table_name="cart_items")
    op.create_unique_constraint("uq_cart_items_cart_variant", "cart_items", ["cart_id", "variant_id"])
    op.drop_index(op.f("ix_cart_items_product_id"), table_name="cart_items")
    op.drop_constraint(op.f("fk_cart_items_product_id_products"), "cart_items", type_="foreignkey")
    op.alter_column("cart_items", "variant_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("cart_items", "product_id")
