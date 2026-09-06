"""halve social video thresholds

Revision ID: 0012_halve_social_video_thresholds
Revises: 0011_update_yimu_video_title
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0012_halve_social_video_thresholds"
down_revision: str | None = "0011_update_yimu_video_title"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _refresh_thresholds(
        {
            ("常州本地", "抖音"): (250, 100, "常州范围抖音：250赞或100收藏"),
            ("常州本地", "微信视频号"): (100, 35, "常州范围微信视频号：100赞或35收藏"),
            ("全国大博主", "抖音"): (2500, 1000, "抖音大博主：2500赞或1000收藏"),
            ("全国大博主", "微信视频号"): (500, 100, "微信视频号大博主：500赞或100收藏"),
        }
    )


def downgrade() -> None:
    _refresh_thresholds(
        {
            ("常州本地", "抖音"): (500, 200, "常州范围抖音：500赞或200收藏"),
            ("常州本地", "微信视频号"): (200, 70, "常州范围微信视频号：200赞或70收藏"),
            ("全国大博主", "抖音"): (5000, 2000, "抖音大博主：5000赞或2000收藏"),
            ("全国大博主", "微信视频号"): (1000, 200, "微信视频号大博主：1000赞或200收藏"),
        }
    )


def _refresh_thresholds(rules: dict[tuple[str, str], tuple[int, int, str]]) -> None:
    connection = op.get_bind()
    rows = connection.execute(
        text("SELECT id, platform, scope, likes, saves FROM social_videos")
    ).mappings()
    for row in rows:
        like_threshold, save_threshold, threshold = rules[(row["scope"], row["platform"])]
        is_hot = row["likes"] >= like_threshold or row["saves"] >= save_threshold
        reason_prefix = "已命中推送阈值" if is_hot else "暂未达标"
        reason = f"{reason_prefix}：{row['likes']}赞、{row['saves']}收藏，规则为{threshold}。"
        connection.execute(
            text(
                """
                UPDATE social_videos
                SET threshold = :threshold, is_hot = :is_hot, reason = :reason
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "threshold": threshold,
                "is_hot": is_hot,
                "reason": reason,
            },
        )
