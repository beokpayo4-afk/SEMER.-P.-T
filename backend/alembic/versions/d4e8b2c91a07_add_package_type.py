"""add holiday package type

Revision ID: d4e8b2c91a07
Revises: c9f3a1e84b20
Create Date: 2026-10-03 15:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e8b2c91a07"
down_revision: Union[str, Sequence[str], None] = "c9f3a1e84b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

package_type = sa.Enum("domestic", "international", name="package_type")


def upgrade() -> None:
    package_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "travel_packages",
        sa.Column(
            "package_type",
            package_type,
            server_default="domestic",
            nullable=False,
        ),
    )
    op.execute("UPDATE travel_packages SET package_type = 'international' WHERE category = 'international'")
    op.create_index(op.f("ix_travel_packages_package_type"), "travel_packages", ["package_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_travel_packages_package_type"), table_name="travel_packages")
    op.drop_column("travel_packages", "package_type")
    package_type.drop(op.get_bind(), checkfirst=True)
