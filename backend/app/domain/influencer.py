from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum


class InfluencerPlatform(StrEnum):
    WECHAT_OFFICIAL = "公众号"
    WECHAT_CHANNELS = "视频号"
    OTHER = "其他"


@dataclass(frozen=True, slots=True)
class Influencer:
    id: int
    name: str
    platform: InfluencerPlatform
    profile_url: str
    note: str
    core_views: list[str]
    style_traits: list[str]
    common_topics: list[str]
    parent_questions: list[str]
    content_count: int
    created_at: datetime
    updated_at: datetime

    def update_profile(
        self,
        *,
        core_views: list[str],
        style_traits: list[str],
        common_topics: list[str],
        parent_questions: list[str],
        content_count: int,
    ) -> "Influencer":
        return replace(
            self,
            core_views=core_views,
            style_traits=style_traits,
            common_topics=common_topics,
            parent_questions=parent_questions,
            content_count=content_count,
            updated_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class InfluencerContent:
    id: int
    influencer_id: int
    title: str
    url: str
    content: str
    summary: str
    created_at: datetime
