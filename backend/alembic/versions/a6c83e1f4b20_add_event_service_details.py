"""add event service details and enquiry fields

Revision ID: a6c83e1f4b20
Revises: f2b71d4c9e08
Create Date: 2026-09-29 14:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a6c83e1f4b20"
down_revision: Union[str, Sequence[str], None] = "f2b71d4c9e08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

event_category = postgresql.ENUM(
    "wedding",
    "anniversary",
    "private_party",
    "planning",
    "decoration",
    "logistics",
    name="event_category",
    create_type=False,
)


def upgrade() -> None:
    event_category.create(op.get_bind(), checkfirst=True)
    op.alter_column("event_services", "name", new_column_name="title")
    op.add_column("event_services", sa.Column("category", event_category, nullable=True))
    op.add_column("event_services", sa.Column("services", sa.Text(), server_default="", nullable=False))
    op.add_column(
        "event_services",
        sa.Column("is_featured", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute("UPDATE event_services SET category = 'wedding' WHERE category IS NULL")
    op.alter_column("event_services", "category", nullable=False)
    op.create_index(op.f("ix_event_services_category"), "event_services", ["category"], unique=False)
    op.create_index(op.f("ix_event_services_is_featured"), "event_services", ["is_featured"], unique=False)
    op.create_table(
        "event_service_images",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("alt_text", sa.String(length=180), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["event_services.id"],
            name=op.f("fk_event_service_images_service_id_event_services"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_service_images")),
    )
    op.create_index(
        op.f("ix_event_service_images_service_id"),
        "event_service_images",
        ["service_id"],
        unique=False,
    )

    op.add_column("event_enquiries", sa.Column("event_type", event_category, nullable=True))
    op.add_column("event_enquiries", sa.Column("location", sa.String(length=180), nullable=True))
    op.add_column("event_enquiries", sa.Column("expected_guests", sa.Integer(), nullable=True))
    op.add_column("event_enquiries", sa.Column("budget_paise", sa.BigInteger(), nullable=True))
    op.add_column("event_enquiries", sa.Column("requirements", sa.Text(), nullable=True))
    op.add_column("event_enquiries", sa.Column("internal_notes", sa.Text(), server_default="", nullable=False))
    op.execute(
        """
        UPDATE event_enquiries
        SET event_type = COALESCE(event_type, 'wedding'),
            event_date = COALESCE(event_date, CURRENT_DATE),
            location = COALESCE(location, 'Unknown'),
            expected_guests = COALESCE(expected_guests, 1),
            budget_paise = COALESCE(budget_paise, 0),
            requirements = COALESCE(requirements, '')
        """
    )
    op.alter_column("event_enquiries", "event_type", nullable=False)
    op.alter_column("event_enquiries", "event_date", nullable=False)
    op.alter_column("event_enquiries", "location", nullable=False)
    op.alter_column("event_enquiries", "expected_guests", nullable=False)
    op.alter_column("event_enquiries", "budget_paise", nullable=False)
    op.alter_column("event_enquiries", "requirements", nullable=False)
    op.create_check_constraint(
        op.f("ck_event_enquiries_guests_positive"),
        "event_enquiries",
        "expected_guests > 0",
    )
    op.create_check_constraint(
        op.f("ck_event_enquiries_budget_non_negative"),
        "event_enquiries",
        "budget_paise >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_event_enquiries_budget_non_negative"), "event_enquiries", type_="check")
    op.drop_constraint(op.f("ck_event_enquiries_guests_positive"), "event_enquiries", type_="check")
    op.drop_column("event_enquiries", "internal_notes")
    op.drop_column("event_enquiries", "requirements")
    op.drop_column("event_enquiries", "budget_paise")
    op.drop_column("event_enquiries", "expected_guests")
    op.drop_column("event_enquiries", "location")
    op.drop_column("event_enquiries", "event_type")
    op.alter_column("event_enquiries", "event_date", nullable=True)
    op.drop_index(op.f("ix_event_service_images_service_id"), table_name="event_service_images")
    op.drop_table("event_service_images")
    op.drop_index(op.f("ix_event_services_is_featured"), table_name="event_services")
    op.drop_index(op.f("ix_event_services_category"), table_name="event_services")
    op.drop_column("event_services", "is_featured")
    op.drop_column("event_services", "services")
    op.drop_column("event_services", "category")
    op.alter_column("event_services", "title", new_column_name="name")
    event_category.drop(op.get_bind(), checkfirst=True)
