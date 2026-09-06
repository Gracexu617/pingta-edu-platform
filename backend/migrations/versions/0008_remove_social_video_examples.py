"""remove social video examples

Revision ID: 0008_remove_social_video_examples
Revises: 0007_create_social_videos
Create Date: 2026-07-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_remove_social_video_examples"
down_revision: str | None = "0007_create_social_videos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM social_videos WHERE title LIKE '真实链接录入示例：%'")


def downgrade() -> None:
    pass
