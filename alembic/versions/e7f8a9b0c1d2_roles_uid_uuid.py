"""roles: integer id -> uuid uid; user_roles.role_id as uuid FK to roles.uid

Revision ID: e7f8a9b0c1d2
Revises: 3c9235604c52
Create Date: 2026-04-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "3c9235604c52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("roles", sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(sa.text("UPDATE roles SET uid = gen_random_uuid()"))
    op.alter_column("roles", "uid", nullable=False)

    op.add_column(
        "user_roles",
        sa.Column("role_uid_temp", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text("""
            UPDATE user_roles ur
            SET role_uid_temp = r.uid
            FROM roles r
            WHERE ur.role_id = r.id
        """)
    )
    op.execute(sa.text("DELETE FROM user_roles WHERE role_uid_temp IS NULL"))
    op.alter_column("user_roles", "role_uid_temp", nullable=False)

    op.execute(sa.text("ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_role_id_fkey"))
    op.drop_column("user_roles", "role_id")
    op.execute(sa.text("ALTER TABLE user_roles RENAME COLUMN role_uid_temp TO role_id"))

    op.drop_constraint("roles_pkey", "roles", type_="primary")
    op.drop_column("roles", "id")
    op.create_primary_key("roles_pkey", "roles", ["uid"])

    op.create_foreign_key(
        "user_roles_role_id_fkey",
        "user_roles",
        "roles",
        ["role_id"],
        ["uid"],
        ondelete="CASCADE",
    )
    op.drop_index(op.f("ix_user_roles_user_id"), table_name="user_roles", if_exists=True)
    op.drop_index(op.f("ix_user_roles_role_id"), table_name="user_roles", if_exists=True)
    op.create_index(op.f("ix_user_roles_user_id"), "user_roles", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("不支持从 roles.uid 降级回自增 id")
