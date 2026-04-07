"""help_documents: docs_relpath pointing to files under repo docs/

Revision ID: i1j2k3l4m5n6
Revises: 1a682359f52c
Create Date: 2026-04-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i1j2k3l4m5n6"
down_revision: Union[str, None] = "1a682359f52c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "help_documents",
        sa.Column("docs_relpath", sa.String(length=512), nullable=True),
    )
    op.create_index("ix_help_documents_docs_relpath", "help_documents", ["docs_relpath"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE help_documents SET docs_relpath = '文档需求/REQUIREMENTS.md'
              WHERE id = 'a0000001-0001-4001-8001-000000000001'::uuid;
            UPDATE help_documents SET docs_relpath = 'message通知/IMPLEMENTATION_PLAN.md'
              WHERE id = 'a0000001-0001-4001-8001-000000000002'::uuid;
            UPDATE help_documents SET docs_relpath = 'FRONTEND_API.md'
              WHERE id = 'a0000001-0001-4001-8001-000000000003'::uuid;
            UPDATE help_documents SET docs_relpath = 'USER_ROLES_DESIGN.md'
              WHERE id = 'a0000001-0001-4001-8001-000000000004'::uuid;
            UPDATE help_documents SET docs_relpath = 'FRONTEND.md'
              WHERE id = 'a0000001-0001-4001-8001-000000000005'::uuid;
            UPDATE help_documents SET docs_relpath = 'ai问答需求/DEV_PLAN.md'
              WHERE id = 'a0000001-0001-4001-8001-000000000006'::uuid;
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_help_documents_docs_relpath", table_name="help_documents")
    op.drop_column("help_documents", "docs_relpath")
