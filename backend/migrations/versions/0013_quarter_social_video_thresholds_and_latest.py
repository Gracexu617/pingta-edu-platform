"""quarter social video thresholds and prefer latest public videos

Revision ID: 0013_quarter_social_video_thresholds_and_latest
Revises: 0012_halve_social_video_thresholds
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0013_quarter_social_video_thresholds_and_latest"
down_revision: str | None = "0012_halve_social_video_thresholds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_MANUAL_URLS = (
    "https://www.douyin.com/video/7440052218193157427",
    "https://www.douyin.com/video/7445524069771037964",
    "https://www.douyin.com/video/7523851044973002025",
    "https://www.douyin.com/video/7491282842338520331",
    "https://www.douyin.com/video/7257442266043645223",
)


def upgrade() -> None:
    connection = op.get_bind()
    for url in OLD_MANUAL_URLS:
        connection.execute(
            text("DELETE FROM social_videos WHERE original_url = :url"),
            {"url": url},
        )
    _refresh_thresholds(
        {
            ("常州本地", "抖音"): (125, 50, "常州范围抖音：125赞或50收藏"),
            ("常州本地", "微信视频号"): (50, 18, "常州范围微信视频号：50赞或18收藏"),
            ("全国大博主", "抖音"): (1250, 500, "抖音大博主：1250赞或500收藏"),
            ("全国大博主", "微信视频号"): (250, 50, "微信视频号大博主：250赞或50收藏"),
        }
    )


def downgrade() -> None:
    _refresh_thresholds(
        {
            ("常州本地", "抖音"): (250, 100, "常州范围抖音：250赞或100收藏"),
            ("常州本地", "微信视频号"): (100, 35, "常州范围微信视频号：100赞或35收藏"),
            ("全国大博主", "抖音"): (2500, 1000, "抖音大博主：2500赞或1000收藏"),
            ("全国大博主", "微信视频号"): (500, 100, "微信视频号大博主：500赞或100收藏"),
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
            {"id": row["id"], "threshold": threshold, "is_hot": is_hot, "reason": reason},
        )
