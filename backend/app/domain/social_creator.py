from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.social_video import SocialVideoPlatform, SocialVideoScope


class SocialCreatorCategory(StrEnum):
    GAOKAO = "高考升学"
    ZHONGKAO = "中考升学"
    CHANGZHOU = "常州本地教育"
    FAMILY_EDUCATION = "家庭教育规划"


@dataclass(frozen=True, slots=True)
class SocialCreator:
    id: int
    name: str
    platform: SocialVideoPlatform
    scope: SocialVideoScope
    category: SocialCreatorCategory
    profile_url: str
    keywords: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime
