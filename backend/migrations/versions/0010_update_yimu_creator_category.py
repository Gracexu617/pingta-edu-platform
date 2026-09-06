"""update yimu creator category

Revision ID: 0010_update_yimu_creator_category
Revises: 0009_create_social_creators
Create Date: 2026-07-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_update_yimu_creator_category"
down_revision: str | None = "0009_create_social_creators"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE social_creators
        SET category = '高考升学',
            keywords = '["高考", "升学", "志愿填报", "专业选择", "家长"]'
        WHERE name = '学习指导-亦木老师'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE social_creators
        SET category = '中考升学',
            keywords = '["中考", "升学", "择校", "志愿填报", "家长"]'
        WHERE name = '学习指导-亦木老师'
        """
    )
