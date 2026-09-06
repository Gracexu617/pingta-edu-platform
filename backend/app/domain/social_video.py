from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SocialVideoPlatform(StrEnum):
    DOUYIN = "抖音"
    WECHAT_CHANNELS = "微信视频号"


class SocialVideoScope(StrEnum):
    NATIONAL_INFLUENCER = "全国大博主"
    CHANGZHOU_LOCAL = "常州本地"


@dataclass(frozen=True, slots=True)
class SocialVideo:
    id: int
    title: str
    creator: str
    platform: SocialVideoPlatform
    scope: SocialVideoScope
    original_url: str
    likes: int
    saves: int
    threshold: str
    is_hot: bool
    reason: str
    transcript: str
    transcript_source: str
    transcript_updated_at: datetime | None
    manuscript: str
    published_at: datetime
    collected_at: datetime
    play_url: str = ""
