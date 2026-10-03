"""add order checkout fields

Revision ID: d8c41f0a6b25
Revises: c4a8e1b27d03
Create Date: 2026-09-29 13:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8c41f0a6b25"
down_revision: Union[str, Sequence[str], None] = "c4a8e1b27d03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'processing'")
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'refunded'")

    op.add_column("orders", sa.Column("billing_address_id", sa.Uuid(), nullable=True))
    op.add_column("orders", sa.Column("customer_name", sa.String(length=120), nullable=True))
    op.add_column("orders", sa.Column("customer_email", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("customer_phone", sa.String(length=20), nullable=True))
    op.add_column(
        "orders",
        sa.Column("discount_paise", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.execute(
        """
        UPDATE orders AS placement
        SET customer_name = account.full_name,
            customer_email = account.email,
            customer_phone = COALESCE(NULLIF(placement.customer_phone, ''), '00000000')
        FROM users AS account
        WHERE placement.user_id = account.id
          AND placement.customer_name IS NULL
        """
    )
    op.execute("UPDATE orders SET customer_name = 'Unknown' WHERE customer_name IS NULL")
    op.execute("UPDATE orders SET customer_email = 'unknown@example.com' WHERE customer_email IS NULL")
    op.execute("UPDATE orders SET customer_phone = '00000000' WHERE customer_phone IS NULL")
    op.alter_column("orders", "customer_name", nullable=False)
    op.alter_column("orders", "customer_email", nullable=False)
    op.alter_column("orders", "customer_phone", nullable=False)
    op.create_foreign_key(
        op.f("fk_orders_billing_address_id_addresses"),
        "orders",
        "addresses",
        ["billing_address_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_orders_billing_address_id"), "orders", ["billing_address_id"], unique=False)
    op.create_check_constraint(op.f("ck_orders_discount_non_negative"), "orders", "discount_paise >= 0")
    op.create_check_constraint(
        op.f("ck_orders_discount_not_above_subtotal"),
        "orders",
        "discount_paise <= subtotal_paise",
    )
    op.create_check_constraint(
        op.f("ck_orders_total_equation"),
        "orders",
        "total_paise = subtotal_paise - discount_paise + shipping_paise + tax_paise",
    )

    op.add_column("order_items", sa.Column("variant_name", sa.String(length=120), nullable=True))
    op.add_column("order_items", sa.Column("list_price_paise", sa.BigInteger(), nullable=True))
    op.execute("UPDATE order_items SET list_price_paise = unit_price_paise WHERE list_price_paise IS NULL")
    op.alter_column("order_items", "list_price_paise", nullable=False)
    op.create_check_constraint(
        op.f("ck_order_items_list_price_non_negative"),
        "order_items",
        "list_price_paise >= 0",
    )
    op.create_check_constraint(
        op.f("ck_order_items_unit_price_not_above_list"),
        "order_items",
        "unit_price_paise <= list_price_paise",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_order_items_unit_price_not_above_list"), "order_items", type_="check")
    op.drop_constraint(op.f("ck_order_items_list_price_non_negative"), "order_items", type_="check")
    op.drop_column("order_items", "list_price_paise")
    op.drop_column("order_items", "variant_name")
    op.drop_constraint(op.f("ck_orders_total_equation"), "orders", type_="check")
    op.drop_constraint(op.f("ck_orders_discount_not_above_subtotal"), "orders", type_="check")
    op.drop_constraint(op.f("ck_orders_discount_non_negative"), "orders", type_="check")
    op.drop_index(op.f("ix_orders_billing_address_id"), table_name="orders")
    op.drop_constraint(op.f("fk_orders_billing_address_id_addresses"), "orders", type_="foreignkey")
    op.drop_column("orders", "discount_paise")
    op.drop_column("orders", "customer_phone")
    op.drop_column("orders", "customer_email")
    op.drop_column("orders", "customer_name")
    op.drop_column("orders", "billing_address_id")
