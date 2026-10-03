"""add travel package details and enquiry fields

Revision ID: f2b71d4c9e08
Revises: e5a90c3b8d17
Create Date: 2026-09-29 14:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2b71d4c9e08"
down_revision: Union[str, Sequence[str], None] = "e5a90c3b8d17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

travel_category = sa.Enum(
    "domestic",
    "international",
    "holiday",
    "customized",
    name="travel_category",
)


def upgrade() -> None:
    travel_category.create(op.get_bind(), checkfirst=True)
    op.add_column("travel_packages", sa.Column("category", travel_category, nullable=True))
    op.add_column("travel_packages", sa.Column("country", sa.String(length=80), server_default="", nullable=False))
    op.add_column("travel_packages", sa.Column("itinerary", sa.Text(), server_default="", nullable=False))
    op.add_column("travel_packages", sa.Column("accommodation", sa.Text(), server_default="", nullable=False))
    op.add_column("travel_packages", sa.Column("transportation", sa.Text(), server_default="", nullable=False))
    op.add_column("travel_packages", sa.Column("activities", sa.Text(), server_default="", nullable=False))
    op.add_column("travel_packages", sa.Column("inclusions", sa.Text(), server_default="", nullable=False))
    op.add_column("travel_packages", sa.Column("exclusions", sa.Text(), server_default="", nullable=False))
    op.add_column(
        "travel_packages",
        sa.Column("is_featured", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute("UPDATE travel_packages SET category = 'domestic' WHERE category IS NULL")
    op.alter_column("travel_packages", "category", nullable=False)
    op.create_index(op.f("ix_travel_packages_category"), "travel_packages", ["category"], unique=False)
    op.create_index(op.f("ix_travel_packages_is_featured"), "travel_packages", ["is_featured"], unique=False)
    op.create_table(
        "travel_package_images",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("alt_text", sa.String(length=180), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["package_id"],
            ["travel_packages.id"],
            name=op.f("fk_travel_package_images_package_id_travel_packages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_travel_package_images")),
    )
    op.create_index(
        op.f("ix_travel_package_images_package_id"),
        "travel_package_images",
        ["package_id"],
        unique=False,
    )

    op.add_column("travel_enquiries", sa.Column("destination", sa.String(length=120), nullable=True))
    op.add_column("travel_enquiries", sa.Column("travel_date", sa.Date(), nullable=True))
    op.add_column("travel_enquiries", sa.Column("travelers", sa.Integer(), nullable=True))
    op.add_column("travel_enquiries", sa.Column("budget_paise", sa.BigInteger(), nullable=True))
    op.execute(
        """
        UPDATE travel_enquiries
        SET destination = COALESCE(destination, 'Unknown'),
            travel_date = COALESCE(travel_date, CURRENT_DATE),
            travelers = COALESCE(travelers, 1),
            budget_paise = COALESCE(budget_paise, 0)
        """
    )
    op.alter_column("travel_enquiries", "destination", nullable=False)
    op.alter_column("travel_enquiries", "travel_date", nullable=False)
    op.alter_column("travel_enquiries", "travelers", nullable=False)
    op.alter_column("travel_enquiries", "budget_paise", nullable=False)
    op.create_check_constraint(
        op.f("ck_travel_enquiries_travelers_positive"),
        "travel_enquiries",
        "travelers > 0",
    )
    op.create_check_constraint(
        op.f("ck_travel_enquiries_budget_non_negative"),
        "travel_enquiries",
        "budget_paise >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_travel_enquiries_budget_non_negative"), "travel_enquiries", type_="check")
    op.drop_constraint(op.f("ck_travel_enquiries_travelers_positive"), "travel_enquiries", type_="check")
    op.drop_column("travel_enquiries", "budget_paise")
    op.drop_column("travel_enquiries", "travelers")
    op.drop_column("travel_enquiries", "travel_date")
    op.drop_column("travel_enquiries", "destination")
    op.drop_index(op.f("ix_travel_package_images_package_id"), table_name="travel_package_images")
    op.drop_table("travel_package_images")
    op.drop_index(op.f("ix_travel_packages_is_featured"), table_name="travel_packages")
    op.drop_index(op.f("ix_travel_packages_category"), table_name="travel_packages")
    op.drop_column("travel_packages", "is_featured")
    op.drop_column("travel_packages", "exclusions")
    op.drop_column("travel_packages", "inclusions")
    op.drop_column("travel_packages", "activities")
    op.drop_column("travel_packages", "transportation")
    op.drop_column("travel_packages", "accommodation")
    op.drop_column("travel_packages", "itinerary")
    op.drop_column("travel_packages", "country")
    op.drop_column("travel_packages", "category")
    travel_category.drop(op.get_bind(), checkfirst=True)
