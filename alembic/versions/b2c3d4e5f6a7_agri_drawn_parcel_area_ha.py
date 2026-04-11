"""agri_drawn_parcel: area_ha（圈地面积 公顷）

Revision ID: b2c3d4e5f6a7
Revises: a7b8c9d0e1f2
Create Date: 2026-04-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agri_drawn_parcel",
        sa.Column("area_ha", sa.Numeric(12, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agri_drawn_parcel", "area_ha")
