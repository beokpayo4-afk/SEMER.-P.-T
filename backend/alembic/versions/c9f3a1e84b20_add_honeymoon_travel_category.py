"""add honeymoon travel category

Revision ID: c9f3a1e84b20
Revises: b8e14f2a7c55
Create Date: 2026-09-30 10:50:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c9f3a1e84b20"
down_revision: Union[str, Sequence[str], None] = "b8e14f2a7c55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE travel_category ADD VALUE IF NOT EXISTS 'honeymoon'")


def downgrade() -> None:
    pass
