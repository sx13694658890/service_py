"""help_documents.upload_storage_path for uploaded markdown

Revision ID: b3c4d5e6f7a8
Revises: ac2ff5488c02
Create Date: 2026-04-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "ac2ff5488c02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "help_documents",
        sa.Column("upload_storage_path", sa.String(length=512), nullable=True),
    )
    op.create_index(
        "ix_help_documents_upload_storage_path",
        "help_documents",
        ["upload_storage_path"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_help_documents_upload_storage_path", table_name="help_documents")
    op.drop_column("help_documents", "upload_storage_path")
