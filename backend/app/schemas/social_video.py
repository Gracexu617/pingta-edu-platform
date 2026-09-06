from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.domain.social_video import SocialVideoPlatform, SocialVideoScope


class SocialVideoCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    creator: str = Field(min_length=1, max_length=120)
    platform: SocialVideoPlatform
    scope: SocialVideoScope
    original_url: HttpUrl
    likes: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    published_at: datetime | None = None


class SocialVideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    creator: str
    platform: SocialVideoPlatform
    scope: SocialVideoScope
    original_url: str
    play_url: str = ""
    likes: int
    saves: int
    threshold: str
    is_hot: bool
    reason: str
    recommendation_score: int = 0
    transcript: str
    transcript_source: str
    transcript_updated_at: datetime | None
    manuscript: str
    published_at: datetime
    collected_at: datetime


class SocialVideoListResponse(BaseModel):
    items: list[SocialVideoResponse]


class SocialVideoCollectResponse(BaseModel):
    created: int
    items: list[SocialVideoResponse]


class SocialVideoCollectionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    finished_at: datetime
    discovered: int
    hot_matched: int
    scope_rejected: int
    duplicate_skipped: int
    created: int
    status: str
    message: str


class SocialVideoCollectionLogListResponse(BaseModel):
    items: list[SocialVideoCollectionLogResponse]


class HotThresholdItem(BaseModel):
    platform: str = Field(min_length=1, max_length=20)
    scope: str = Field(min_length=1, max_length=20)
    likes: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)


class HotThresholdUpdateRequest(BaseModel):
    items: list[HotThresholdItem]


class HotThresholdResponse(BaseModel):
    items: list[HotThresholdItem]
