"""create social creators

Revision ID: 0009_create_social_creators
Revises: 0008_remove_social_video_examples
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_create_social_creators"
down_revision: str | None = "0008_remove_social_video_examples"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "social_creators",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("platform", sa.String(length=24), nullable=False),
        sa.Column("scope", sa.String(length=24), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("profile_url", sa.String(length=800), nullable=False, server_default=""),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_social_creators_enabled", "social_creators", ["enabled"])
    op.create_index("ix_social_creators_name", "social_creators", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_social_creators_name", table_name="social_creators")
    op.drop_index("ix_social_creators_enabled", table_name="social_creators")
    op.drop_table("social_creators")
