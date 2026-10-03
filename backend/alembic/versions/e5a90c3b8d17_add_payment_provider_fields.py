"""add payment provider fields

Revision ID: e5a90c3b8d17
Revises: d8c41f0a6b25
Create Date: 2026-09-29 13:55:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5a90c3b8d17"
down_revision: Union[str, Sequence[str], None] = "d8c41f0a6b25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False))
    op.add_column("payments", sa.Column("provider", sa.String(length=32), server_default="manual", nullable=False))
    op.add_column("payments", sa.Column("transaction_id", sa.String(length=120), nullable=True))
    op.execute(
        """
        UPDATE payments
        SET transaction_id = provider_reference
        WHERE transaction_id IS NULL
          AND provider_reference IS NOT NULL
        """
    )
    op.drop_column("payments", "provider_reference")
    op.create_index(
        "uq_payments_transaction_id",
        "payments",
        ["transaction_id"],
        unique=True,
        postgresql_where=sa.text("transaction_id IS NOT NULL"),
    )
    op.create_check_constraint(op.f("ck_payments_currency_code"), "payments", "char_length(currency) = 3")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_payments_currency_code"), "payments", type_="check")
    op.drop_index("uq_payments_transaction_id", table_name="payments")
    op.add_column("payments", sa.Column("provider_reference", sa.String(length=120), nullable=True))
    op.execute(
        """
        UPDATE payments
        SET provider_reference = transaction_id
        WHERE provider_reference IS NULL
          AND transaction_id IS NOT NULL
        """
    )
    op.drop_column("payments", "transaction_id")
    op.drop_column("payments", "provider")
    op.drop_column("payments", "currency")
