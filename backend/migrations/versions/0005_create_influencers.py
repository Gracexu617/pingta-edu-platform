"""create influencers

Revision ID: 0005_create_influencers
Revises: 0004_add_material_keywords
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_create_influencers"
down_revision: str | None = "0004_add_material_keywords"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "influencers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("profile_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("core_views", sa.JSON(), nullable=False),
        sa.Column("style_traits", sa.JSON(), nullable=False),
        sa.Column("common_topics", sa.JSON(), nullable=False),
        sa.Column("parent_questions", sa.JSON(), nullable=False),
        sa.Column("content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_influencers_name"),
    )
    op.create_index("ix_influencers_name", "influencers", ["name"])
    op.create_table(
        "influencer_contents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("influencer_id", sa.Integer(), sa.ForeignKey("influencers.id"), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_influencer_contents_influencer_id",
        "influencer_contents",
        ["influencer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_influencer_contents_influencer_id", table_name="influencer_contents")
    op.drop_table("influencer_contents")
    op.drop_index("ix_influencers_name", table_name="influencers")
    op.drop_table("influencers")
