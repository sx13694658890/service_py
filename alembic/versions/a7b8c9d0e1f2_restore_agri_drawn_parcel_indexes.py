"""restore agri_drawn_parcel indexes (误 autogenerate 曾删除)

Revision ID: a7b8c9d0e1f2
Revises: 64136ce8772c
Create Date: 2026-04-11

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "64136ce8772c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_agri_drawn_parcel_user_id ON agri_drawn_parcel (user_id)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_agri_drawn_parcel_region_id ON agri_drawn_parcel (region_id)"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ix_agri_drawn_parcel_region_id"))
    op.execute(text("DROP INDEX IF EXISTS ix_agri_drawn_parcel_user_id"))
