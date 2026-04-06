"""users: integer id -> UUID user_id; user_roles.user_id UUID FK

Revision ID: f8a9b0c1d2e3
Revises: 0003
Create Date: 2026-04-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("new_pk", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(sa.text("UPDATE users SET new_pk = gen_random_uuid()"))
    op.alter_column("users", "new_pk", nullable=False)

    op.add_column(
        "user_roles",
        sa.Column("user_uuid", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text("""
            UPDATE user_roles ur
            SET user_uuid = u.new_pk
            FROM users u
            WHERE ur.user_id = u.id
        """)
    )
    op.alter_column("user_roles", "user_uuid", nullable=False)

    op.execute(sa.text("ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_user_id_fkey"))

    op.drop_column("user_roles", "user_id")
    op.execute(sa.text("ALTER TABLE user_roles RENAME COLUMN user_uuid TO user_id"))

    op.drop_constraint("users_pkey", "users", type_="primary")
    op.drop_column("users", "id")
    op.execute(sa.text("ALTER TABLE users RENAME COLUMN new_pk TO user_id"))
    op.create_primary_key("users_pkey", "users", ["user_id"])

    op.create_foreign_key(
        "user_roles_user_id_fkey",
        "user_roles",
        "users",
        ["user_id"],
        ["user_id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_user_roles_user_id"), "user_roles", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("不支持从 UUID user_id 自动降级回自增 id")
