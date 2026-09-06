"""create collect tasks table

Revision ID: 0003_create_collect_tasks
Revises: 0002_create_materials
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_create_collect_tasks"
down_revision: str | None = "0002_create_materials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collect_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_collect_tasks_source_id", "collect_tasks", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_collect_tasks_source_id", table_name="collect_tasks")
    op.drop_table("collect_tasks")
