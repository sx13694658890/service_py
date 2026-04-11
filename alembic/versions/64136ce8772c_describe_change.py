"""describe_change

Revision ID: 64136ce8772c
Revises: c4d5e6f7a8b9
Create Date: 2026-04-11 21:52:41.942564

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64136ce8772c'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 原 autogenerate 误删索引；已改为 no-op，索引由 a7b8c9d0e1f2 以 if_not_exists 恢复/补齐。
    pass


def downgrade() -> None:
    pass
