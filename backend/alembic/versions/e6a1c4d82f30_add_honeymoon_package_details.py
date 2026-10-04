"""add honeymoon package details

Revision ID: e6a1c4d82f30
Revises: d4e8b2c91a07
Create Date: 2026-10-03 15:25:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6a1c4d82f30"
down_revision: Union[str, Sequence[str], None] = "d4e8b2c91a07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

package_category = sa.Enum(
    "holiday",
    "honeymoon",
    "family",
    "adventure",
    "beach",
    "luxury",
    "pilgrimage",
    "group",
    name="package_category",
)


def upgrade() -> None:
    package_category.create(op.get_bind(), checkfirst=True)
    op.add_column("travel_packages", sa.Column("package_category", package_category, nullable=True))
    op.create_index(op.f("ix_travel_packages_package_category"), "travel_packages", ["package_category"], unique=False)
    for name in (
        "romantic_highlights",
        "hotel_category",
        "room_type",
        "couple_experiences",
        "honeymoon_inclusions",
    ):
        op.add_column(
            "travel_packages",
            sa.Column(name, sa.Text(), server_default="", nullable=False),
        )
    op.execute("UPDATE travel_packages SET package_category = 'holiday' WHERE category = 'holiday'")
    op.execute("UPDATE travel_packages SET package_category = 'honeymoon' WHERE category = 'honeymoon'")


def downgrade() -> None:
    for name in (
        "honeymoon_inclusions",
        "couple_experiences",
        "room_type",
        "hotel_category",
        "romantic_highlights",
    ):
        op.drop_column("travel_packages", name)
    op.drop_index(op.f("ix_travel_packages_package_category"), table_name="travel_packages")
    op.drop_column("travel_packages", "package_category")
    package_category.drop(op.get_bind(), checkfirst=True)
