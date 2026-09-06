"""add social video transcripts

Revision ID: 0014_add_social_video_transcripts
Revises: 0013_quarter_social_video_thresholds_and_latest
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_add_social_video_transcripts"
down_revision: str | None = "0013_quarter_social_video_thresholds_and_latest"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "social_videos",
        sa.Column("transcript", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "social_videos",
        sa.Column("transcript_source", sa.String(length=40), nullable=False, server_default=""),
    )
    op.add_column(
        "social_videos",
        sa.Column("transcript_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("social_videos", "transcript_updated_at")
    op.drop_column("social_videos", "transcript_source")
    op.drop_column("social_videos", "transcript")
