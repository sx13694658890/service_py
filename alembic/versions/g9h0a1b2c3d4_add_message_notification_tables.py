"""add messages and user_messages for in-app notifications

Revision ID: g9h0a1b2c3d4
Revises: fc2e28ddeeaa
Create Date: 2026-04-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g9h0a1b2c3d4"
down_revision: Union[str, None] = "fc2e28ddeeaa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("priority", sa.String(length=16), server_default="normal", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_category", "messages", ["category"], unique=False)
    op.create_index("ix_messages_created_at", "messages", ["created_at"], unique=False)
    op.create_index("ix_messages_category_created_at", "messages", ["category", "created_at"], unique=False)

    op.create_table(
        "user_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "message_id", name="uq_user_messages_user_message"),
    )
    op.create_index("ix_user_messages_user_id_created_at", "user_messages", ["user_id", "created_at"], unique=False)
    op.create_index("ix_user_messages_user_id_is_read", "user_messages", ["user_id", "is_read"], unique=False)
    op.create_index(
        "ix_user_messages_user_deleted_created",
        "user_messages",
        ["user_id", "is_deleted", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_messages_user_deleted_created", table_name="user_messages")
    op.drop_index("ix_user_messages_user_id_is_read", table_name="user_messages")
    op.drop_index("ix_user_messages_user_id_created_at", table_name="user_messages")
    op.drop_table("user_messages")
    op.drop_index("ix_messages_category_created_at", table_name="messages")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_category", table_name="messages")
    op.drop_table("messages")
