"""create materials table

Revision ID: 0002_create_materials
Revises: 0001_create_sources
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_create_materials"
down_revision: str | None = "0001_create_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_materials_title", "materials", ["title"])


def downgrade() -> None:
    op.drop_index("ix_materials_title", table_name="materials")
    op.drop_table("materials")
