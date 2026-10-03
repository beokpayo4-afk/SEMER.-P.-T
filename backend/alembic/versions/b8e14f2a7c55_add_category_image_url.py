"""add category image url

Revision ID: b8e14f2a7c55
Revises: a6c83e1f4b20
Create Date: 2026-09-29 15:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8e14f2a7c55"
down_revision: Union[str, Sequence[str], None] = "a6c83e1f4b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("image_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("categories", "image_url")
