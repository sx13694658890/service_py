"""add help_documents for docs center list/detail

Revision ID: h0i1j2k3l4m5
Revises: g9h0a1b2c3d4
Create Date: 2026-04-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "h0i1j2k3l4m5"
down_revision: Union[str, None] = "g9h0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "help_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("required_role_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_help_documents_category", "help_documents", ["category"], unique=False)
    op.create_index("ix_help_documents_updated_at", "help_documents", ["updated_at"], unique=False)

    op.execute(
        sa.text(
            """
            INSERT INTO help_documents
                (id, title, summary, category, score, tags, required_role_codes, body)
            VALUES
            (
                'a0000001-0001-4001-8001-000000000001'::uuid,
                'Windows 使用入门',
                '从桌面、窗口到常用快捷键的快速上手指南。',
                '使用文档',
                4.8,
                '["E","C","A","S","W","+3"]'::jsonb,
                NULL,
                '# Windows 使用入门\n\n欢迎阅读本文档。'
            ),
            (
                'a0000001-0001-4001-8001-000000000002'::uuid,
                '回访流程说明',
                '外呼回访标准流程、话术要点与记录规范。',
                '回访',
                4.5,
                '["流程","质检"]'::jsonb,
                NULL,
                '# 回访流程\n\n按步骤完成客户回访并记录结果。'
            ),
            (
                'a0000001-0001-4001-8001-000000000003'::uuid,
                '对账与开票',
                '财务对账周期、差异处理与开票申请入口说明。',
                '财务',
                4.2,
                '["对账","发票"]'::jsonb,
                NULL,
                '# 对账与开票\n\n详见财务制度。'
            ),
            (
                'a0000001-0001-4001-8001-000000000004'::uuid,
                '用户权限模型',
                '角色、权限继承与常见授权场景说明。',
                '用户',
                4.0,
                '["权限","角色"]'::jsonb,
                NULL,
                '# 用户权限\n\nRBAC 模型简介。'
            ),
            (
                'a0000001-0001-4001-8001-000000000005'::uuid,
                '常见问题 FAQ',
                '登录失败、密码重置与浏览器兼容等高频问题。',
                '使用文档',
                NULL,
                '["FAQ","帮助"]'::jsonb,
                NULL,
                '# FAQ\n\n如仍无法解决请联系管理员。'
            ),
            (
                'a0000001-0001-4001-8001-000000000006'::uuid,
                '管理员内部手册',
                '仅管理员可见：系统配置与审计要点。',
                '使用文档',
                5.0,
                '["内部"]'::jsonb,
                '["admin"]'::jsonb,
                '# 内部手册\n\n敏感操作须留痕。'
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_help_documents_updated_at", table_name="help_documents")
    op.drop_index("ix_help_documents_category", table_name="help_documents")
    op.drop_table("help_documents")
