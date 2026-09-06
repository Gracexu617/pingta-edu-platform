"""create changzhou news

Revision ID: 0006_create_changzhou_news
Revises: 0005_create_influencers
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_create_changzhou_news"
down_revision: str | None = "0005_create_influencers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "changzhou_news",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("importance", sa.String(length=16), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_changzhou_news_title", "changzhou_news", ["title"])


def downgrade() -> None:
    op.drop_index("ix_changzhou_news_title", table_name="changzhou_news")
    op.drop_table("changzhou_news")
