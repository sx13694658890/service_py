"""agri: user drawn parcels (圈地存储)

Revision ID: c4d5e6f7a8b9
Revises: bf8026755c7d
Create Date: 2026-04-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "bf8026755c7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agri_drawn_parcel",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("region_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("geom", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extra", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["region_id"], ["agri_region.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agri_drawn_parcel_user_id", "agri_drawn_parcel", ["user_id"], unique=False)
    op.create_index(
        "ix_agri_drawn_parcel_region_id", "agri_drawn_parcel", ["region_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_agri_drawn_parcel_region_id", table_name="agri_drawn_parcel")
    op.drop_index("ix_agri_drawn_parcel_user_id", table_name="agri_drawn_parcel")
    op.drop_table("agri_drawn_parcel")
