"""update yimu video title

Revision ID: 0011_update_yimu_video_title
Revises: 0010_update_yimu_creator_category
Create Date: 2026-07-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_update_yimu_video_title"
down_revision: str | None = "0010_update_yimu_creator_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE social_videos
        SET title = '高考志愿填报指导视频'
        WHERE original_url = 'https://jingxuan.douyin.com/m/video/7630685782566538496'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE social_videos
        SET title = '中考志愿填报指导视频'
        WHERE original_url = 'https://jingxuan.douyin.com/m/video/7630685782566538496'
        """
    )
