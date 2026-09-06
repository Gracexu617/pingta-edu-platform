"""create social videos

Revision ID: 0007_create_social_videos
Revises: 0006_create_changzhou_news
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_create_social_videos"
down_revision: str | None = "0006_create_changzhou_news"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "social_videos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("creator", sa.String(length=120), nullable=False),
        sa.Column("platform", sa.String(length=24), nullable=False),
        sa.Column("scope", sa.String(length=24), nullable=False),
        sa.Column("original_url", sa.String(length=800), nullable=False),
        sa.Column("likes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("saves", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("threshold", sa.String(length=80), nullable=False),
        sa.Column("is_hot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_social_videos_creator", "social_videos", ["creator"])
    op.create_index("ix_social_videos_is_hot", "social_videos", ["is_hot"])
    op.create_index("ix_social_videos_title", "social_videos", ["title"])


def downgrade() -> None:
    op.drop_index("ix_social_videos_title", table_name="social_videos")
    op.drop_index("ix_social_videos_is_hot", table_name="social_videos")
    op.drop_index("ix_social_videos_creator", table_name="social_videos")
    op.drop_table("social_videos")
